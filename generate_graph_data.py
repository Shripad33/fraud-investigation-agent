import os
import pandas as pd


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
GRAPH_DIR = os.path.join(DATA_DIR, "tigergraph")

os.makedirs(GRAPH_DIR, exist_ok=True)


print("=" * 70)
print("TIGERGRAPH DATA PREPARATION")
print("=" * 70)


# ============================================================
# 1. LOAD SOURCE DATA
# ============================================================

transactions_path = os.path.join(DATA_DIR, "transactions.csv")
identity_path = os.path.join(DATA_DIR, "identity.csv")
closed_cases_path = os.path.join(DATA_DIR, "closed_cases_history.csv")


print("\n[1/7] Loading transactions.csv...")

transactions = pd.read_csv(
    transactions_path,
    usecols=[
        "TransactionID",
        "customer_id",
        "ts",
        "channel",
        "risk_score",
        "card1",
        "P_emaildomain",
        "addr1",
    ],
)

# IMPORTANT:
# Make TransactionID the same datatype used by identity.csv.
transactions["TransactionID"] = (
    transactions["TransactionID"]
    .astype(str)
    .str.strip()
)

print(f"Transactions loaded: {len(transactions):,}")


print("\n[2/7] Loading identity.csv...")

identity = pd.read_csv(
    identity_path,
    usecols=[
        "TransactionID",
        "DeviceType",
        "DeviceInfo",
    ],
)

# IMPORTANT:
# Fix the datatype mismatch that caused the previous error.
identity["TransactionID"] = (
    identity["TransactionID"]
    .astype(str)
    .str.strip()
)

print(f"Identity records loaded: {len(identity):,}")


print("\n[3/7] Loading closed case history...")

closed_cases = pd.read_csv(
    closed_cases_path
)

print(f"Closed cases loaded: {len(closed_cases):,}")


# ============================================================
# 2. CLEAN TRANSACTIONS
# ============================================================

print("\n[4/7] Cleaning transaction data...")

transactions["customer_id"] = (
    transactions["customer_id"]
    .fillna("UNKNOWN_CUSTOMER")
    .astype(str)
    .str.strip()
)

transactions["card1"] = (
    transactions["card1"]
    .fillna(-1)
)

transactions["P_emaildomain"] = (
    transactions["P_emaildomain"]
    .fillna("UNKNOWN_EMAIL")
    .astype(str)
    .str.strip()
)

transactions["addr1"] = (
    transactions["addr1"]
    .fillna(-1)
)

transactions["channel"] = (
    transactions["channel"]
    .fillna("unknown")
    .astype(str)
    .str.strip()
)

transactions["risk_score"] = (
    pd.to_numeric(
        transactions["risk_score"],
        errors="coerce"
    )
    .fillna(0.0)
)

transactions["ts"] = (
    transactions["ts"]
    .fillna("")
    .astype(str)
    .str.strip()
)


# ============================================================
# 3. BUILD CUSTOMER VERTICES
# ============================================================

print("\n[5/7] Creating Customer vertices...")

customers = (
    transactions[
        ["customer_id"]
    ]
    .drop_duplicates()
    .copy()
)

customers["customer_name"] = customers["customer_id"]

customers = customers[
    [
        "customer_id",
        "customer_name",
    ]
]

customers.to_csv(
    os.path.join(
        GRAPH_DIR,
        "Customer.csv"
    ),
    index=False,
)

print(
    f"Customer vertices: "
    f"{len(customers):,}"
)


# ============================================================
# 4. BUILD CARD VERTICES
# ============================================================

print("\nCreating Card vertices...")

cards = (
    transactions[
        ["card1"]
    ]
    .drop_duplicates()
    .copy()
)

cards["card_id"] = (
    cards["card1"]
    .apply(lambda x: f"CARD_{x}")
)

cards["card_type"] = "payment_card"

cards = cards[
    [
        "card_id",
        "card_type",
    ]
]

cards.to_csv(
    os.path.join(
        GRAPH_DIR,
        "Card.csv"
    ),
    index=False,
)

print(
    f"Card vertices: "
    f"{len(cards):,}"
)


# ============================================================
# 5. BUILD TRANSACTION VERTICES
# ============================================================

print("\nCreating Transaction vertices...")

transaction_vertices = transactions[
    [
        "TransactionID",
        "ts",
        "channel",
        "risk_score",
    ]
].copy()

transaction_vertices = transaction_vertices.rename(
    columns={
        "TransactionID": "transaction_id",
        "ts": "timestamp",
    }
)

transaction_vertices.to_csv(
    os.path.join(
        GRAPH_DIR,
        "Transaction.csv"
    ),
    index=False,
)

print(
    f"Transaction vertices: "
    f"{len(transaction_vertices):,}"
)


# ============================================================
# 6. MERGE IDENTITY INFORMATION
# ============================================================

print("\nMerging transaction + identity data...")

transaction_identity = transactions.merge(
    identity,
    on="TransactionID",
    how="left",
)

print(
    f"Merged records: "
    f"{len(transaction_identity):,}"
)


transaction_identity["DeviceType"] = (
    transaction_identity["DeviceType"]
    .fillna("UNKNOWN_DEVICE_TYPE")
    .astype(str)
    .str.strip()
)

transaction_identity["DeviceInfo"] = (
    transaction_identity["DeviceInfo"]
    .fillna("UNKNOWN_DEVICE")
    .astype(str)
    .str.strip()
)


# ============================================================
# 7. DEVICE PROFILE VERTICES
# ============================================================

print("\nCreating DeviceProfile vertices...")

devices = (
    transaction_identity[
        [
            "DeviceInfo",
            "DeviceType",
        ]
    ]
    .drop_duplicates()
    .copy()
)

devices["device_id"] = (
    devices["DeviceInfo"]
    .apply(
        lambda x: f"DEVICE_{x}"
    )
)

devices = devices[
    [
        "device_id",
        "DeviceType",
        "DeviceInfo",
    ]
]

devices = devices.drop_duplicates(
    subset=["device_id"]
)

devices.to_csv(
    os.path.join(
        GRAPH_DIR,
        "DeviceProfile.csv"
    ),
    index=False,
)

print(
    f"Device vertices: "
    f"{len(devices):,}"
)


# ============================================================
# 8. EMAIL DOMAIN VERTICES
# ============================================================

print("\nCreating EmailDomain vertices...")

emails = (
    transactions[
        ["P_emaildomain"]
    ]
    .drop_duplicates()
    .copy()
)

emails["email_id"] = (
    emails["P_emaildomain"]
    .apply(
        lambda x: f"EMAIL_{x}"
    )
)

emails["domain"] = (
    emails["P_emaildomain"]
)

emails = emails[
    [
        "email_id",
        "domain",
    ]
]

emails.to_csv(
    os.path.join(
        GRAPH_DIR,
        "EmailDomain.csv"
    ),
    index=False,
)

print(
    f"Email domain vertices: "
    f"{len(emails):,}"
)


# ============================================================
# 9. BILLING REGION VERTICES
# ============================================================

print("\nCreating BillingRegion vertices...")

regions = (
    transactions[
        ["addr1"]
    ]
    .drop_duplicates()
    .copy()
)

regions["region_id"] = (
    regions["addr1"]
    .apply(
        lambda x: f"REGION_{x}"
    )
)

regions["region_code"] = (
    regions["addr1"]
    .astype(str)
)

regions = regions[
    [
        "region_id",
        "region_code",
    ]
]

regions.to_csv(
    os.path.join(
        GRAPH_DIR,
        "BillingRegion.csv"
    ),
    index=False,
)

print(
    f"Billing region vertices: "
    f"{len(regions):,}"
)


# ============================================================
# 10. CLOSED CASE VERTICES
# ============================================================

print("\nCreating ClosedCase vertices...")

if len(closed_cases) > 0:

    case_vertices = (
        closed_cases
        .copy()
    )

    case_vertices["case_id"] = (
        case_vertices["case_id"]
        .astype(str)
        .str.strip()
    )

    wanted_columns = [
        "case_id",
        "opened_at",
        "closed_at",
        "outcome",
        "pattern",
        "n_txns",
        "exposure_usd",
        "report_filed",
    ]

    available_columns = [
        column
        for column in wanted_columns
        if column in case_vertices.columns
    ]

    case_vertices = case_vertices[
        available_columns
    ]

    case_vertices.to_csv(
        os.path.join(
            GRAPH_DIR,
            "ClosedCase.csv"
        ),
        index=False,
    )

    print(
        f"ClosedCase vertices: "
        f"{len(case_vertices):,}"
    )

else:

    print("No closed cases found.")


# ============================================================
# 11. EDGE: Customer -> Card
# ============================================================

print("\nCreating OWNS edges...")

owns = transactions[
    [
        "customer_id",
        "card1",
    ]
].drop_duplicates()

owns["card_id"] = (
    owns["card1"]
    .apply(
        lambda x: f"CARD_{x}"
    )
)

owns = owns[
    [
        "customer_id",
        "card_id",
    ]
]

owns.to_csv(
    os.path.join(
        GRAPH_DIR,
        "OWNS.csv"
    ),
    index=False,
)

print(
    f"OWNS edges: "
    f"{len(owns):,}"
)


# ============================================================
# 12. EDGE: Customer -> Transaction
# ============================================================

print("\nCreating MADE edges...")

made = transactions[
    [
        "customer_id",
        "TransactionID",
    ]
].copy()

made = made.rename(
    columns={
        "TransactionID": "transaction_id"
    }
)

made.to_csv(
    os.path.join(
        GRAPH_DIR,
        "MADE.csv"
    ),
    index=False,
)

print(
    f"MADE edges: "
    f"{len(made):,}"
)


# ============================================================
# 13. EDGE: Transaction -> Card
# ============================================================

print("\nCreating ON_CARD edges...")

on_card = transactions[
    [
        "TransactionID",
        "card1",
    ]
].copy()

on_card["card_id"] = (
    on_card["card1"]
    .apply(
        lambda x: f"CARD_{x}"
    )
)

on_card = on_card[
    [
        "TransactionID",
        "card_id",
    ]
]

on_card = on_card.rename(
    columns={
        "TransactionID": "transaction_id"
    }
)

on_card.to_csv(
    os.path.join(
        GRAPH_DIR,
        "ON_CARD.csv"
    ),
    index=False,
)

print(
    f"ON_CARD edges: "
    f"{len(on_card):,}"
)


# ============================================================
# 14. EDGE: Transaction -> Device
# ============================================================

print("\nCreating FROM_DEVICE edges...")

from_device = transaction_identity[
    [
        "TransactionID",
        "DeviceInfo",
    ]
].copy()

from_device["device_id"] = (
    from_device["DeviceInfo"]
    .apply(
        lambda x: f"DEVICE_{x}"
    )
)

from_device = from_device[
    [
        "TransactionID",
        "device_id",
    ]
]

from_device = from_device.rename(
    columns={
        "TransactionID": "transaction_id"
    }
)

from_device.to_csv(
    os.path.join(
        GRAPH_DIR,
        "FROM_DEVICE.csv"
    ),
    index=False,
)

print(
    f"FROM_DEVICE edges: "
    f"{len(from_device):,}"
)


# ============================================================
# 15. EDGE: Transaction -> Email
# ============================================================

print("\nCreating PURCHASER_EMAIL edges...")

purchaser_email = transactions[
    [
        "TransactionID",
        "P_emaildomain",
    ]
].copy()

purchaser_email["email_id"] = (
    purchaser_email["P_emaildomain"]
    .apply(
        lambda x: f"EMAIL_{x}"
    )
)

purchaser_email = purchaser_email[
    [
        "TransactionID",
        "email_id",
    ]
]

purchaser_email = purchaser_email.rename(
    columns={
        "TransactionID": "transaction_id"
    }
)

purchaser_email.to_csv(
    os.path.join(
        GRAPH_DIR,
        "PURCHASER_EMAIL.csv"
    ),
    index=False,
)

print(
    f"PURCHASER_EMAIL edges: "
    f"{len(purchaser_email):,}"
)


# ============================================================
# 16. EDGE: Transaction -> Billing Region
# ============================================================

print("\nCreating BILLED_IN edges...")

billed_in = transactions[
    [
        "TransactionID",
        "addr1",
    ]
].copy()

billed_in["region_id"] = (
    billed_in["addr1"]
    .apply(
        lambda x: f"REGION_{x}"
    )
)

billed_in = billed_in[
    [
        "TransactionID",
        "region_id",
    ]
]

billed_in = billed_in.rename(
    columns={
        "TransactionID": "transaction_id"
    }
)

billed_in.to_csv(
    os.path.join(
        GRAPH_DIR,
        "BILLED_IN.csv"
    ),
    index=False,
)

print(
    f"BILLED_IN edges: "
    f"{len(billed_in):,}"
)


# ============================================================
# 17. EDGE: Transaction -> Closed Case
# ============================================================

print("\nCreating INVOLVES edges...")

involves_rows = []

if len(closed_cases) > 0:

    for _, row in closed_cases.iterrows():

        case_id = str(
            row["case_id"]
        ).strip()

        txn_ids = row.get(
            "txn_ids",
            ""
        )

        if pd.isna(txn_ids):
            continue

        txn_ids = str(
            txn_ids
        )

        txn_ids = txn_ids.replace(
            ";",
            ","
        )

        for txn_id in txn_ids.split(","):

            txn_id = txn_id.strip()

            if not txn_id:
                continue

            involves_rows.append(
                {
                    "transaction_id": txn_id,
                    "case_id": case_id,
                }
            )


involves = pd.DataFrame(
    involves_rows,
    columns=[
        "transaction_id",
        "case_id",
    ],
)

involves.to_csv(
    os.path.join(
        GRAPH_DIR,
        "INVOLVES.csv"
    ),
    index=False,
)

print(
    f"INVOLVES edges: "
    f"{len(involves):,}"
)


# ============================================================
# 18. EDGE: Transaction -> Transaction
# ============================================================

print("\nCreating NEXT edges...")

ordered = transactions[
    [
        "TransactionID",
        "customer_id",
        "ts",
    ]
].copy()

ordered["ts"] = pd.to_datetime(
    ordered["ts"],
    errors="coerce",
)

ordered = ordered.dropna(
    subset=["ts"]
)

ordered = ordered.sort_values(
    [
        "customer_id",
        "ts",
    ]
)

ordered["next_transaction"] = (
    ordered
    .groupby("customer_id")["TransactionID"]
    .shift(-1)
)

next_ts = (
    ordered
    .groupby("customer_id")["ts"]
    .shift(-1)
)

next_edges = ordered[
    ordered["next_transaction"].notna()
].copy()

next_edges["sequence_gap_seconds"] = (
    next_ts.loc[next_edges.index]
    - next_edges["ts"]
).dt.total_seconds()

next_edges = next_edges[
    [
        "TransactionID",
        "next_transaction",
        "sequence_gap_seconds",
    ]
]

next_edges = next_edges.rename(
    columns={
        "TransactionID": "from_transaction",
        "next_transaction": "to_transaction",
    }
)

next_edges.to_csv(
    os.path.join(
        GRAPH_DIR,
        "NEXT.csv"
    ),
    index=False,
)

print(
    f"NEXT edges: "
    f"{len(next_edges):,}"
)


# ============================================================
# 19. EDGE: Card -> Card
# ============================================================

print("\nCreating CONNECTED_TO edges...")

card_customer = transactions[
    [
        "customer_id",
        "card1",
    ]
].drop_duplicates()

card_pairs = card_customer.merge(
    card_customer,
    on="customer_id",
    suffixes=("_a", "_b"),
)

card_pairs = card_pairs[
    card_pairs["card1_a"]
    != card_pairs["card1_b"]
]

card_pairs["from_card"] = (
    card_pairs["card1_a"]
    .apply(
        lambda x: f"CARD_{x}"
    )
)

card_pairs["to_card"] = (
    card_pairs["card1_b"]
    .apply(
        lambda x: f"CARD_{x}"
    )
)

connected = card_pairs[
    [
        "from_card",
        "to_card",
    ]
].drop_duplicates()

connected.to_csv(
    os.path.join(
        GRAPH_DIR,
        "CONNECTED_TO.csv"
    ),
    index=False,
)

print(
    f"CONNECTED_TO edges: "
    f"{len(connected):,}"
)


# ============================================================
# 20. FINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("GRAPH DATA GENERATION COMPLETE")
print("=" * 70)

for filename in sorted(
    os.listdir(GRAPH_DIR)
):

    if filename.endswith(".csv"):

        filepath = os.path.join(
            GRAPH_DIR,
            filename
        )

        try:

            rows = len(
                pd.read_csv(
                    filepath
                )
            )

        except Exception:

            rows = "?"

        print(
            f"{filename:<30} {rows}"
        )


print("\nOutput directory:")
print(GRAPH_DIR)

print("\nNext step:")
print(
    "Upload the generated CSV files "
    "into TigerGraph."
)