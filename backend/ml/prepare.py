import pandas as pd

df = pd.read_csv("data/paysim.csv")

# Keep only the two types where fraud happens
df = df[df["type"].isin(["TRANSFER", "CASH_OUT"])].copy()

# Turn type into a number: TRANSFER = 1, CASH_OUT = 0
df["type"] = (df["type"] == "TRANSFER").astype(int)

# New clues: does the money add up correctly?
df["errorOrig"] = df["newbalanceOrig"] + df["amount"] - df["oldbalanceOrg"]
df["errorDest"] = df["oldbalanceDest"] + df["amount"] - df["newbalanceDest"]

# Hour of the day
df["hour"] = df["step"] % 24

# Remove columns the model doesn't need
df = df.drop(columns=["nameOrig", "nameDest", "isFlaggedFraud", "step"])

print("Shape:", df.shape)
print("Fraud %:", round(df["isFraud"].mean() * 100, 2))
df.to_csv("data/prepared.csv", index=False)
print("Saved data/prepared.csv")
