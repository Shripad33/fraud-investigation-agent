import pandas as pd
from pathlib import Path

source = Path("data/transactions.csv")
output = Path("data/transactions_demo.csv")

customers = {
    "C07297",
    "C11891",
    "C12382",
    "C09933",
    "C02923",
    "C08623",
    "C08106",
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
    matches = chunk[
        chunk["customer_id"].astype(str).isin(customers)
    ]

    if not matches.empty:
        found.append(matches)

result = pd.concat(found, ignore_index=True)

result.to_csv(output, index=False)

print("\n================================")
print("CUSTOMER HISTORY DATASET CREATED")
print("================================")
print("Rows:", len(result))
print("Customers:", result["customer_id"].nunique())
print("File:", output)

print("\nRows per customer:")
print(result.groupby("customer_id").size().to_string())
