import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, average_precision_score, confusion_matrix
from xgboost import XGBClassifier

df = pd.read_csv("data/prepared.csv")
X = df.drop(columns=["isFraud"])
y = df["isFraud"]

# 80% to learn from, 20% to test on
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

# Tell the model fraud is rare, so it pays extra attention to it
ratio = (y_train == 0).sum() / (y_train == 1).sum()

model = XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.1,
    scale_pos_weight=ratio, eval_metric="aucpr",
    n_jobs=-1, random_state=42
)
model.fit(X_train, y_train)

probs = model.predict_proba(X_test)[:, 1]
preds = (probs >= 0.5).astype(int)

print("PR-AUC:", round(average_precision_score(y_test, probs), 4))
print("\nConfusion matrix:\n", confusion_matrix(y_test, preds))
print("\n", classification_report(y_test, preds, digits=4))

joblib.dump(model, "models/xgb_model.pkl")
joblib.dump(list(X.columns), "models/features.pkl")
print("Model saved!")