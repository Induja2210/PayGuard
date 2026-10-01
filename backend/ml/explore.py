import pandas as pd

df = pd.read_csv("data/paysim.csv")
print("Shape:", df.shape)
print(df.head())
print("\nFraud count:\n", df["isFraud"].value_counts())
print("\nFraud by type:\n", df.groupby("type")["isFraud"].sum())