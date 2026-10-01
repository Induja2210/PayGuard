import json
import sqlite3
from datetime import datetime

import joblib
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="PayGuard API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

model = joblib.load("models/xgb_model.pkl")
features = joblib.load("models/features.pkl")
sample = pd.read_csv("data/sample_feed.csv")
DB = "payguard.db"


# ---------- Database ----------
def init_db():
    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT, type TEXT, amount REAL,
            oldbalanceOrg REAL, newbalanceOrig REAL,
            oldbalanceDest REAL, newbalanceDest REAL, step INTEGER,
            risk REAL, label TEXT, reasons TEXT,
            status TEXT, actual INTEGER
        )
    """)
    con.commit()
    con.close()


init_db()


def fetch(query, params=()):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    data = [dict(r) for r in con.execute(query, params)]
    con.close()
    for d in data:
        if "reasons" in d:
            d["reasons"] = json.loads(d["reasons"])
    return data


# ---------- Models ----------
class Transaction(BaseModel):
    type: str
    amount: float
    oldbalanceOrg: float
    newbalanceOrig: float
    oldbalanceDest: float
    newbalanceDest: float
    step: int = 1


class Review(BaseModel):
    decision: str  # "fraud" or "safe"


# ---------- Scoring ----------
def make_features(t: Transaction):
    return pd.DataFrame([{
        "type": 1 if t.type == "TRANSFER" else 0,
        "amount": t.amount,
        "oldbalanceOrg": t.oldbalanceOrg,
        "newbalanceOrig": t.newbalanceOrig,
        "oldbalanceDest": t.oldbalanceDest,
        "newbalanceDest": t.newbalanceDest,
        "errorOrig": t.newbalanceOrig + t.amount - t.oldbalanceOrg,
        "errorDest": t.oldbalanceDest + t.amount - t.newbalanceDest,
        "hour": t.step % 24,
    }])[features]


def plain_reason(name, row):
    if name == "errorOrig":
        if abs(row["errorOrig"]) < 1:
            return "The sender's entire balance was moved out in one go"
        return "The sender's balances don't add up after this payment"
    if name == "errorDest":
        return "The receiver's balance didn't change as expected"
    if name == "newbalanceOrig":
        if row["newbalanceOrig"] == 0:
            return "The sender's account was left at zero"
        return f"Sender's balance after payment: {row['newbalanceOrig']:,.0f}"
    if name == "amount":
        return f"Large amount for this account: {row['amount']:,.0f}"
    if name == "oldbalanceOrg":
        return f"Sender had {row['oldbalanceOrg']:,.0f} before the payment"
    if name in ("oldbalanceDest", "newbalanceDest"):
        return "The receiver account's balance pattern looks unusual"
    if name == "type":
        return "Transfers and cash-outs are where fraud happens"
    if name == "hour":
        return f"Made at an unusual hour ({int(row['hour'])}:00)"
    return name


def score(t: Transaction):
    if t.type not in ("TRANSFER", "CASH_OUT"):
        return {"risk": 0.0, "label": "safe",
                "reasons": ["This transaction type has no fraud history"]}
    X = make_features(t)
    risk = float(model.predict_proba(X)[0, 1])
    shap_values = model.get_booster().predict(xgb.DMatrix(X), pred_contribs=True)[0][:-1]
    impact = pd.Series(shap_values, index=features).sort_values(ascending=False)
    row = X.iloc[0]
    reasons = [plain_reason(n, row) for n, v in impact.head(3).items() if v > 0]
    if risk < 0.5:
        reasons = ["No strong fraud signals found"]
    return {"risk": round(risk * 100, 1),
            "label": "fraud" if risk >= 0.5 else "safe",
            "reasons": reasons}


def save(t: Transaction, result, actual=None):
    con = sqlite3.connect(DB)
    cur = con.execute(
        """INSERT INTO transactions (created_at, type, amount, oldbalanceOrg,
           newbalanceOrig, oldbalanceDest, newbalanceDest, step, risk, label,
           reasons, status, actual) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (datetime.now().isoformat(timespec="seconds"), t.type, t.amount,
         t.oldbalanceOrg, t.newbalanceOrig, t.oldbalanceDest, t.newbalanceDest,
         t.step, result["risk"], result["label"], json.dumps(result["reasons"]),
         "pending" if result["label"] == "fraud" else "cleared", actual),
    )
    con.commit()
    new_id = cur.lastrowid
    con.close()
    return new_id


# ---------- Endpoints ----------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
def predict(t: Transaction):
    result = score(t)
    result["id"] = save(t, result)
    return result


@app.post("/simulate")
def simulate():
    r = sample.sample(1).iloc[0]
    t = Transaction(
        type=r["type"], amount=float(r["amount"]),
        oldbalanceOrg=float(r["oldbalanceOrg"]), newbalanceOrig=float(r["newbalanceOrig"]),
        oldbalanceDest=float(r["oldbalanceDest"]), newbalanceDest=float(r["newbalanceDest"]),
        step=int(r["step"]),
    )
    result = score(t)
    result["id"] = save(t, result, actual=int(r["isFraud"]))
    return result


@app.get("/transactions")
def transactions(limit: int = 50):
    return fetch("SELECT * FROM transactions ORDER BY id DESC LIMIT ?", (limit,))


@app.get("/queue")
def queue():
    return fetch("SELECT * FROM transactions WHERE label='fraud' AND status='pending' "
                 "ORDER BY risk DESC")


@app.post("/transactions/{tx_id}/review")
def review(tx_id: int, body: Review):
    if body.decision not in ("fraud", "safe"):
        raise HTTPException(400, "decision must be 'fraud' or 'safe'")
    status = "confirmed_fraud" if body.decision == "fraud" else "marked_safe"
    con = sqlite3.connect(DB)
    con.execute("UPDATE transactions SET status=? WHERE id=?", (status, tx_id))
    con.commit()
    con.close()
    return {"id": tx_id, "status": status}


@app.get("/metrics")
def metrics():
    c = fetch("""SELECT
        COUNT(*) AS total,
        SUM(label='fraud') AS flagged,
        SUM(status='confirmed_fraud') AS confirmed,
        SUM(status='marked_safe') AS marked_safe,
        SUM(label='fraud' AND actual=1) AS tp,
        SUM(label='fraud' AND actual=0) AS fp,
        SUM(label='safe' AND actual=1) AS fn
        FROM transactions""")[0]
    c = {k: (v or 0) for k, v in c.items()}
    c["precision"] = round(c["tp"] / (c["tp"] + c["fp"]) * 100, 1) if (c["tp"] + c["fp"]) else None
    c["recall"] = round(c["tp"] / (c["tp"] + c["fn"]) * 100, 1) if (c["tp"] + c["fn"]) else None
    return c