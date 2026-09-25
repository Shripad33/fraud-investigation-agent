import pandas as pd
from pathlib import Path

source = Path("data/transactions.csv")
output = Path("data/transactions_demo.csv")

needed = {
    "3514030",
    "3478782",
    "3530164",
    "3583227",
    "3523199",
    "3476682",
    "3514948",
}

columns = [
    "TransactionID",
    "TransactionDT",
    "TransactionAmt",
    "ProductCD",
    "addr1",
    "addr2",
    "customer_id",
    "ts",
    "channel",
    "risk_score",
]

found = []

for chunk in pd.read_csv(
    source,
    usecols=columns,
    chunksize=100000
):
    chunk["TransactionID_str"] = chunk["TransactionID"].astype(str)

    matches = chunk[
        chunk["TransactionID_str"].isin(needed)
    ].drop(columns=["TransactionID_str"])

    if not matches.empty:
        found.append(matches)
        print("Found:", matches["TransactionID"].astype(int).tolist())

result = pd.concat(found, ignore_index=True)

result.to_csv(output, index=False)

print("\n================================")
print("DEMO DATASET CREATED")
print("================================")
print("Rows:", len(result))
print("File:", output)
print(result[["TransactionID", "customer_id"]].to_string(index=False))
