import json
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

TRANSACTIONS_FILE = DATA_DIR / "transactions.csv"
INDEX_FILE = OUTPUT_DIR / "transaction_index.json"

CHUNK_SIZE = 100_000


def build_index():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("BUILDING TRANSACTION INDEX")
    print("=" * 60)

    customer_index = {}
    transaction_index = {}
    region_index = {}

    total_rows = 0

    print(f"\nReading:")
    print(TRANSACTIONS_FILE)
    print("\nThis may take a few minutes...\n")

    for chunk_number, chunk in enumerate(
        pd.read_csv(
            TRANSACTIONS_FILE,
            usecols=[
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
            ],
            chunksize=CHUNK_SIZE,
        ),
        start=1,
    ):
        total_rows += len(chunk)

        for row in chunk.itertuples(index=False):

            transaction_id = str(int(row.TransactionID))
            customer_id = str(row.customer_id)
            region = str(row.addr1)

            transaction_index[transaction_id] = {
                "TransactionID": int(row.TransactionID),
                "TransactionDT": int(row.TransactionDT),
                "TransactionAmt": float(row.TransactionAmt),
                "ProductCD": str(row.ProductCD),
                "addr1": region,
                "addr2": (
                    int(row.addr2)
                    if pd.notna(row.addr2)
                    else None
                ),
                "customer_id": customer_id,
                "ts": str(row.ts),
                "channel": str(row.channel),
                "risk_score": float(row.risk_score),
            }

            customer_index.setdefault(
                customer_id,
                []
            ).append(transaction_id)

            if region != "nan":
                region_index.setdefault(
                    region,
                    []
                ).append(transaction_id)

        print(
            f"Chunk {chunk_number:>3} | "
            f"Rows indexed: {total_rows:,}"
        )

    index = {
        "metadata": {
            "total_transactions": total_rows,
            "description": (
                "Local investigation index generated "
                "from transactions.csv"
            ),
        },
        "customer_index": customer_index,
        "transaction_index": transaction_index,
        "region_index": region_index,
    }

    print("\nWriting index...")

    with open(
        INDEX_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            index,
            f,
            ensure_ascii=False,
        )

    print("\n" + "=" * 60)
    print("INDEX BUILD COMPLETE")
    print("=" * 60)

    print(f"Transactions : {total_rows:,}")
    print(f"Customers    : {len(customer_index):,}")
    print(f"Regions      : {len(region_index):,}")
    print(f"Index file   : {INDEX_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    build_index()