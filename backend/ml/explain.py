import pandas as pd
import joblib
import xgboost as xgb

model = joblib.load("models/xgb_model.pkl")
features = joblib.load("models/features.pkl")
df = pd.read_csv("data/prepared.csv")

# Simple names for each feature
labels = {
    "type": "Transaction type",
    "amount": "Amount",
    "oldbalanceOrg": "Sender balance before",
    "newbalanceOrig": "Sender balance after",
    "oldbalanceDest": "Receiver balance before",
    "newbalanceDest": "Receiver balance after",
    "errorOrig": "Sender balance mismatch",
    "errorDest": "Receiver balance mismatch",
    "hour": "Hour of day",
}

# Take 3 fraud examples to test
X = df[df["isFraud"] == 1].head(3)[features]

probs = model.predict_proba(X)[:, 1]
shap_values = model.get_booster().predict(xgb.DMatrix(X), pred_contribs=True)

for i in range(len(X)):
    print(f"\nTransaction {i+1}: fraud risk = {probs[i]*100:.1f}%")
    impact = pd.Series(shap_values[i][:-1], index=features).sort_values(ascending=False)
    print("Top reasons:")
    for name, value in impact.head(3).items():
        print(f"  - {labels[name]}: {X.iloc[i][name]:,.0f} (impact +{value:.2f})")