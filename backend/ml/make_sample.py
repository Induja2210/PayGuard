import pandas as pd

df = pd.read_csv("data/paysim.csv")
df = df[df["type"].isin(["TRANSFER", "CASH_OUT"])]

fraud = df[df["isFraud"] == 1].sample(200, random_state=1)
safe = df[df["isFraud"] == 0].sample(1800, random_state=1)

sample = pd.concat([fraud, safe]).sample(frac=1, random_state=1)
sample.to_csv("data/sample_feed.csv", index=False)
print("Saved", len(sample), "rows")