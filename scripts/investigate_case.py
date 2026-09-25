import argparse
import json
import math
import time
from pathlib import Path

import pandas as pd

from decision_engine import build_case_output, save_case


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = BASE_DIR / "outputs"
CASES_DIR = BASE_DIR / "cases"

CASE_PACK_PATH = DATA_DIR / "case_pack.csv"
TRANSACTIONS_PATH = DATA_DIR / "transactions.csv"
IDENTITY_PATH = DATA_DIR / "identity.csv"
CLOSED_CASES_PATH = DATA_DIR / "closed_cases_history.csv"

TRANSACTION_INDEX_PATH = (
    OUTPUTS_DIR / "transaction_index.json"
)


# ============================================================
# GLOBAL CACHE
# ============================================================

_TRANSACTION_INDEX_CACHE = None
_IDENTITY_CACHE = None
_CLOSED_CASES_CACHE = None


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        result = float(value)

        if pd.isna(result):
            return default

        if not math.isfinite(result):
            return default

        return result

    except (TypeError, ValueError):
        return default


def safe_string(value, default=""):
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    value = str(value).strip()

    if value.lower() == "nan":
        return default

    return value


def normalize_text(value):
    return safe_string(value).strip().lower()


def unique_non_empty(values):
    result = []

    for value in values or []:
        value = safe_string(value)

        if not value:
            continue

        if value not in result:
            result.append(value)

    return result


def safe_datetime(value):
    return pd.to_datetime(
        value,
        errors="coerce",
    )


# ============================================================
# LOAD CASE
# ============================================================

def load_case(case_id):
    if not CASE_PACK_PATH.exists():
        raise FileNotFoundError(
            f"Case pack not found: {CASE_PACK_PATH}"
        )

    cases = pd.read_csv(
        CASE_PACK_PATH,
        low_memory=False,
    )

    if "case_id" not in cases.columns:
        raise ValueError(
            "case_pack.csv does not contain 'case_id'."
        )

    matches = cases[
        cases["case_id"].astype(str)
        == str(case_id)
    ]

    if matches.empty:
        raise ValueError(
            f"Case {case_id} was not found in "
            f"{CASE_PACK_PATH}"
        )

    row = matches.iloc[0].to_dict()

    required_fields = [
        "case_id",
        "opened_at",
        "trigger_type",
        "trigger_text",
        "flagged_txn_id",
        "card_id",
        "customer_id",
        "risk_score",
    ]

    missing = [
        field
        for field in required_fields
        if field not in row
    ]

    if missing:
        raise ValueError(
            "Missing required case fields: "
            + ", ".join(missing)
        )

    return row


# ============================================================
# TRANSACTION INDEX
# ============================================================

def load_transaction_index():
    global _TRANSACTION_INDEX_CACHE

    if _TRANSACTION_INDEX_CACHE is not None:
        return _TRANSACTION_INDEX_CACHE

    if not TRANSACTION_INDEX_PATH.exists():
        raise FileNotFoundError(
            "Transaction index not found:\n"
            f"{TRANSACTION_INDEX_PATH}\n\n"
            "Run:\n"
            "python .\\scripts\\build_index.py"
        )

    with open(
        TRANSACTION_INDEX_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    _TRANSACTION_INDEX_CACHE = data

    return data


# ============================================================
# CUSTOMER TRANSACTIONS
# ============================================================

def load_customer_transactions(
    customer_id,
    transaction_index,
):
    customer_id = safe_string(customer_id)

    customer_index = transaction_index.get(
        "customer_index",
        {},
    )

    transaction_lookup = transaction_index.get(
        "transaction_index",
        {},
    )

    transaction_ids = customer_index.get(
        customer_id,
        [],
    )

    records = []

    for txn_id in transaction_ids:
        txn = transaction_lookup.get(
            str(txn_id)
        )

        if txn is not None:
            records.append(txn)

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records)


# ============================================================
# FLAGGED TRANSACTION
# ============================================================

def get_flagged_transaction(
    case,
    transaction_index,
):
    txn_id = safe_string(
        case.get("flagged_txn_id")
    )

    transaction_lookup = transaction_index.get(
        "transaction_index",
        {},
    )

    txn = transaction_lookup.get(
        txn_id
    )

    if txn is None:
        raise ValueError(
            f"Flagged transaction {txn_id} "
            "was not found in transaction_index.json."
        )

    return txn


# ============================================================
# CUSTOMER HISTORY ANALYSIS
# ============================================================

def analyze_customer_history(
    customer_transactions,
    flagged_txn,
):
    if (
        customer_transactions is None
        or customer_transactions.empty
    ):
        return {
            "transaction_count": 0,
            "average_amount": 0.0,
            "median_amount": 0.0,
            "max_amount": 0.0,
            "flagged_amount": safe_float(
                flagged_txn.get(
                    "TransactionAmt"
                )
            ),
            "flagged_amount_percentile": 0.0,
        }

    df = customer_transactions.copy()

    amounts = pd.to_numeric(
        df.get(
            "TransactionAmt",
            pd.Series(dtype=float),
        ),
        errors="coerce",
    ).dropna()

    flagged_amount = safe_float(
        flagged_txn.get(
            "TransactionAmt"
        )
    )

    if amounts.empty:
        return {
            "transaction_count": len(df),
            "average_amount": 0.0,
            "median_amount": 0.0,
            "max_amount": 0.0,
            "flagged_amount": flagged_amount,
            "flagged_amount_percentile": 0.0,
        }

    percentile = (
        (amounts <= flagged_amount).sum()
        / len(amounts)
        * 100
    )

    return {
        "transaction_count": int(len(df)),
        "average_amount": round(
            float(amounts.mean()),
            2,
        ),
        "median_amount": round(
            float(amounts.median()),
            2,
        ),
        "max_amount": round(
            float(amounts.max()),
            2,
        ),
        "flagged_amount": round(
            flagged_amount,
            2,
        ),
        "flagged_amount_percentile": round(
            float(percentile),
            2,
        ),
    }


# ============================================================
# TRANSACTION BEHAVIOR
# ============================================================

def analyze_transaction_behavior(
    flagged_txn,
    customer_transactions,
):
    flagged_amount = safe_float(
        flagged_txn.get(
            "TransactionAmt"
        )
    )

    flagged_channel = normalize_text(
        flagged_txn.get(
            "channel"
        )
    )

    product_code = safe_string(
        flagged_txn.get(
            "ProductCD"
        )
    )

    if (
        customer_transactions is None
        or customer_transactions.empty
    ):
        return {
            "flagged_amount": flagged_amount,
            "flagged_channel": flagged_channel,
            "unusual_amount": False,
            "product_code": product_code,
        }

    amounts = pd.to_numeric(
        customer_transactions.get(
            "TransactionAmt",
            pd.Series(dtype=float),
        ),
        errors="coerce",
    )

    amounts = amounts.dropna()

    unusual_amount = False

    if not amounts.empty:
        average = float(
            amounts.mean()
        )
        median = float(
            amounts.median()
        )

        # Conservative local heuristic.
        if average > 0:
            if (
                flagged_amount > average * 2.5
                or flagged_amount < average * 0.20
            ):
                unusual_amount = True

        if median > 0:
            if (
                flagged_amount > median * 3
                or flagged_amount < median * 0.20
            ):
                unusual_amount = True

    return {
        "flagged_amount": flagged_amount,
        "flagged_channel": flagged_channel,
        "unusual_amount": unusual_amount,
        "product_code": product_code,
    }


# ============================================================
# TIME ANALYSIS
# ============================================================

def analyze_time_behavior(
    flagged_txn,
    customer_transactions,
):
    flagged_time = safe_datetime(
        flagged_txn.get("ts")
    )

    if pd.isna(flagged_time):
        flagged_time = safe_datetime(
            flagged_txn.get(
                "TransactionDT"
            )
        )

    if (
        pd.isna(flagged_time)
        or customer_transactions is None
        or customer_transactions.empty
    ):
        return {
            "transactions_1h": 0,
            "transactions_24h": 0,
            "transactions_48h": 0,
        }

    df = customer_transactions.copy()

    if "ts" in df.columns:
        timestamps = pd.to_datetime(
            df["ts"],
            errors="coerce",
        )
    else:
        timestamps = pd.to_datetime(
            df.get(
                "TransactionDT",
                pd.Series(
                    dtype="datetime64[ns]"
                ),
            ),
            errors="coerce",
        )

    valid = timestamps.notna()

    if not valid.any():
        return {
            "transactions_1h": 0,
            "transactions_24h": 0,
            "transactions_48h": 0,
        }

    delta_hours = (
        (
            timestamps[valid]
            - flagged_time
        )
        .abs()
        .dt.total_seconds()
        / 3600
    )

    return {
        "transactions_1h": int(
            (delta_hours <= 1).sum()
        ),
        "transactions_24h": int(
            (delta_hours <= 24).sum()
        ),
        "transactions_48h": int(
            (delta_hours <= 48).sum()
        ),
    }


# ============================================================
# CHANNEL ANALYSIS
# ============================================================

def analyze_channel_behavior(
    flagged_txn,
    customer_transactions,
):
    flagged_channel = normalize_text(
        flagged_txn.get(
            "channel"
        )
    )

    online_count = 0
    in_person_count = 0

    if (
        customer_transactions is not None
        and not customer_transactions.empty
        and "channel" in customer_transactions.columns
    ):
        channels = (
            customer_transactions["channel"]
            .astype(str)
            .str.lower()
            .str.strip()
        )

        online_count = int(
            (channels == "online").sum()
        )

        in_person_count = int(
            (
                channels == "in_person"
            ).sum()
        )

    return {
        "flagged_channel": flagged_channel,
        "online_count": online_count,
        "in_person_count": in_person_count,
        "mixed_channel": (
            online_count > 0
            and in_person_count > 0
        ),
    }


# ============================================================
# REGION ANALYSIS
# ============================================================

def analyze_region_behavior(
    flagged_txn,
    customer_transactions,
):
    flagged_region = safe_string(
        flagged_txn.get(
            "addr1"
        )
    )

    if not flagged_region:
        return {
            "flagged_region": "",
            "new_region": False,
            "known_region": False,
            "historical_region_count": 0,
        }

    if (
        customer_transactions is None
        or customer_transactions.empty
        or "addr1" not in customer_transactions.columns
    ):
        return {
            "flagged_region": flagged_region,
            "new_region": True,
            "known_region": False,
            "historical_region_count": 0,
        }

    regions = (
        customer_transactions["addr1"]
        .astype(str)
        .str.strip()
    )

    matches = regions[
        regions == flagged_region
    ]

    count = int(
        len(matches)
    )

    return {
        "flagged_region": flagged_region,
        "new_region": count == 0,
        "known_region": count > 0,
        "historical_region_count": count,
    }


# ============================================================
# IDENTITY DATA
# ============================================================

def load_identity_for_transactions(
    transaction_ids,
):
    """
    Read identity.csv once per process and retain only the
    requested transaction IDs.
    """

    global _IDENTITY_CACHE

    requested = {
        safe_string(txn_id)
        for txn_id in transaction_ids
        if safe_string(txn_id)
    }

    if not requested:
        return pd.DataFrame()

    if _IDENTITY_CACHE is not None:
        if "TransactionID" in _IDENTITY_CACHE.columns:
            return _IDENTITY_CACHE[
                _IDENTITY_CACHE[
                    "TransactionID"
                ]
                .astype(str)
                .isin(requested)
            ].copy()

    if not IDENTITY_PATH.exists():
        return pd.DataFrame()

    chunks = []

    try:
        for chunk in pd.read_csv(
            IDENTITY_PATH,
            chunksize=100000,
            low_memory=False,
        ):
            if "TransactionID" not in chunk.columns:
                continue

            mask = (
                chunk["TransactionID"]
                .astype(str)
                .isin(requested)
            )

            if mask.any():
                chunks.append(
                    chunk.loc[mask].copy()
                )

    except Exception as exc:
        print(
            f"Warning: identity.csv could not be fully read: {exc}"
        )
        return pd.DataFrame()

    if chunks:
        result = pd.concat(
            chunks,
            ignore_index=True,
        )
    else:
        result = pd.DataFrame()

    # Cache only the matching rows needed by the current
    # investigation. This prevents repeatedly scanning the
    # same huge identity file during the same process.
    _IDENTITY_CACHE = result.copy()

    return result


# ============================================================
# IDENTITY EXTRACTION
# ============================================================

def extract_identity_info(
    identity_df,
    flagged_txn_id,
):
    if (
        identity_df is None
        or identity_df.empty
    ):
        return {
            "available": False,
            "new_identity": False,
            "proxy": False,
            "device_info": "",
            "device_type": "",
            "browser": "",
            "os": "",
            "screen": "",
            "match_status": "",
            "identity_anomalies": [],
            "device_profiles": [],
        }

    if "TransactionID" not in identity_df.columns:
        return {
            "available": False,
            "new_identity": False,
            "proxy": False,
            "device_info": "",
            "device_type": "",
            "browser": "",
            "os": "",
            "screen": "",
            "match_status": "",
            "identity_anomalies": [],
            "device_profiles": [],
        }

    rows = identity_df[
        identity_df["TransactionID"]
        .astype(str)
        == safe_string(flagged_txn_id)
    ]

    if rows.empty:
        return {
            "available": False,
            "new_identity": False,
            "proxy": False,
            "device_info": "",
            "device_type": "",
            "browser": "",
            "os": "",
            "screen": "",
            "match_status": "",
            "identity_anomalies": [],
            "device_profiles": [],
        }

    row = rows.iloc[0]

    id_15 = normalize_text(
        row.get("id_15")
    )

    id_23 = normalize_text(
        row.get("id_23")
    )

    id_34 = safe_string(
        row.get("id_34")
    )

    device_info = safe_string(
        row.get("DeviceInfo")
    )

    device_type = safe_string(
        row.get("DeviceType")
    )

    browser = safe_string(
        row.get("id_31")
    )

    operating_system = safe_string(
        row.get("id_30")
    )

    screen = safe_string(
        row.get("id_33")
    )

    anomalies = []

    if id_15 == "new":
        anomalies.append(
            "new_identity"
        )

    if id_23 == "proxy":
        anomalies.append(
            "proxy"
        )

    if id_34:
        normalized_match = normalize_text(
            id_34
        )

        if normalized_match not in {
            "match",
            "match_status",
            "found",
            "nan",
        }:
            anomalies.append(
                f"match_status:{id_34}"
            )

    device_profiles = []

    if device_info:
        device_profiles.append(
            device_info
        )

    return {
        "available": True,
        "new_identity": (
            id_15 == "new"
        ),
        "proxy": (
            id_23 == "proxy"
        ),
        "device_info": device_info,
        "device_type": device_type,
        "browser": browser,
        "os": operating_system,
        "screen": screen,
        "match_status": id_34,
        "identity_anomalies": unique_non_empty(
            anomalies
        ),
        "device_profiles": unique_non_empty(
            device_profiles
        ),
    }


# ============================================================
# CLOSED CASE HISTORY
# ============================================================

def load_closed_cases():
    global _CLOSED_CASES_CACHE

    if _CLOSED_CASES_CACHE is not None:
        return _CLOSED_CASES_CACHE

    if not CLOSED_CASES_PATH.exists():
        return pd.DataFrame()

    try:
        _CLOSED_CASES_CACHE = pd.read_csv(
            CLOSED_CASES_PATH,
            low_memory=False,
        )
    except Exception as exc:
        print(
            "Warning: could not load "
            f"closed_cases_history.csv: {exc}"
        )
        return pd.DataFrame()

    return _CLOSED_CASES_CACHE


# ============================================================
# PRIOR CASE ANALYSIS
# ============================================================

def analyze_prior_cases(
    case,
    flagged_txn,
    customer_transactions,
):
    """
    Find relevant historical cases rather than simply taking
    the first 20 rows of the closed-case dataset.

    Relevance:
      same card       +100
      same customer    +80
      same pattern     +30
      similar exposure +20
      same region      +15
      same channel     +10
    """

    closed_cases = load_closed_cases()

    if (
        closed_cases is None
        or closed_cases.empty
    ):
        return {
            "confirmed_fraud_cases": 0,
            "cleared_cases": 0,
            "cases": [],
            "direct_history_cases": [],
            "pattern_hint": "",
        }

    customer_id = safe_string(
        case.get("customer_id")
    )

    card_id = safe_string(
        case.get("card_id")
    )

    region = safe_string(
        flagged_txn.get("addr1")
    )

    channel = normalize_text(
        flagged_txn.get("channel")
    )

    amount = safe_float(
        flagged_txn.get("TransactionAmt")
    )

    # --------------------------------------------------------
    # Column discovery
    # --------------------------------------------------------

    def first_existing(columns):
        for column in columns:
            if column in closed_cases.columns:
                return column
        return None

    case_id_col = first_existing([
        "case_id",
        "CaseID",
        "closed_case_id",
        "ClosedCaseID",
    ])

    customer_col = first_existing([
        "customer_id",
        "CustomerID",
        "customer",
    ])

    card_col = first_existing([
        "card_id",
        "CardID",
        "card",
    ])

    pattern_col = first_existing([
        "pattern",
        "fraud_pattern",
        "fraud_type",
    ])

    status_col = first_existing([
        "status",
        "case_status",
        "verdict",
        "outcome",
    ])

    amount_col = first_existing([
        "exposure_usd",
        "total_amount_usd",
        "amount",
        "TransactionAmt",
    ])

    region_col = first_existing([
        "addr1",
        "region",
        "billing_region",
    ])

    channel_col = first_existing([
        "channel",
    ])

    scored_cases = []

    for _, row in closed_cases.iterrows():

        score = 0

        row_customer = (
            safe_string(row.get(customer_col))
            if customer_col
            else ""
        )

        row_card = (
            safe_string(row.get(card_col))
            if card_col
            else ""
        )

        row_pattern = (
            normalize_text(row.get(pattern_col))
            if pattern_col
            else ""
        )

        row_status = (
            normalize_text(row.get(status_col))
            if status_col
            else ""
        )

        row_region = (
            safe_string(row.get(region_col))
            if region_col
            else ""
        )

        row_channel = (
            normalize_text(row.get(channel_col))
            if channel_col
            else ""
        )

        row_amount = (
            safe_float(row.get(amount_col))
            if amount_col
            else 0.0
        )

        if (
            customer_id
            and row_customer == customer_id
        ):
            score += 80

        if (
            card_id
            and row_card == card_id
        ):
            score += 100

        if (
            row_pattern
            and row_pattern != "none"
            and row_pattern == ""
        ):
            score += 30

        if (
            region
            and row_region
            and row_region == region
        ):
            score += 15

        if (
            channel
            and row_channel
            and row_channel == channel
        ):
            score += 10

        if (
            amount > 0
            and row_amount > 0
        ):
            difference = abs(
                row_amount - amount
            ) / max(
                amount,
                0.01,
            )

            if difference <= 0.25:
                score += 20

        if score <= 0:
            continue

        case_id_value = (
            safe_string(
                row.get(case_id_col)
            )
            if case_id_col
            else ""
        )

        if not case_id_value:
            case_id_value = "historical_case"

        scored_cases.append({
            "case_id": case_id_value,
            "relevance_score": score,
            "status": (
                row_status
                if row_status
                else ""
            ),
            "pattern": (
                row_pattern
                if row_pattern
                else ""
            ),
            "customer_id": row_customer,
            "card_id": row_card,
        })

    scored_cases.sort(
        key=lambda item: (
            item.get(
                "relevance_score",
                0,
            ),
            item.get(
                "case_id",
                "",
            ),
        ),
        reverse=True,
    )

    top_cases = scored_cases[:20]

    # --------------------------------------------------------
    # Direct customer/card history
    # --------------------------------------------------------

    direct_history_cases = [
        item
        for item in scored_cases
        if (
            (
                customer_id
                and item.get(
                    "customer_id"
                )
                == customer_id
            )
            or (
                card_id
                and item.get(
                    "card_id"
                )
                == card_id
            )
        )
    ]

    # --------------------------------------------------------
    # Confirmed / cleared counts
    #
    # IMPORTANT:
    # Only directly relevant customer/card cases count toward
    # the temporary fraud heuristic.
    # --------------------------------------------------------

    confirmed_fraud_cases = 0
    cleared_cases = 0

    for item in direct_history_cases:

        status = normalize_text(
            item.get("status")
        )

        if status in {
            "confirmed_fraud",
            "fraud",
            "confirmed fraud",
        }:
            confirmed_fraud_cases += 1

        elif status in {
            "cleared",
            "legitimate",
            "closed_legitimate",
            "none",
        }:
            cleared_cases += 1

    # --------------------------------------------------------
    # Pattern hint
    # --------------------------------------------------------

    pattern_hint = ""

    for item in top_cases:

        candidate = normalize_text(
            item.get("pattern")
        )

        if candidate and candidate != "none":
            pattern_hint = candidate
            break

    # --------------------------------------------------------
    # Fallback similar cases
    #
    # If no direct history exists, keep amount/channel/region
    # related cases as contextual evidence.
    # --------------------------------------------------------

    if not top_cases:
        fallback = []

        for _, row in closed_cases.iterrows():

            row_amount = safe_float(
                row.get(amount_col)
                if amount_col
                else 0
            )

            if (
                amount <= 0
                or row_amount <= 0
            ):
                continue

            difference = abs(
                row_amount - amount
            ) / max(
                amount,
                0.01,
            )

            if difference > 0.25:
                continue

            row_case_id = (
                safe_string(
                    row.get(case_id_col)
                )
                if case_id_col
                else ""
            )

            row_pattern = (
                normalize_text(
                    row.get(pattern_col)
                )
                if pattern_col
                else ""
            )

            row_status = (
                normalize_text(
                    row.get(status_col)
                )
                if status_col
                else ""
            )

            fallback.append({
                "case_id": (
                    row_case_id
                    or "historical_case"
                ),
                "relevance_score": 20,
                "status": row_status,
                "pattern": row_pattern,
                "customer_id": (
                    safe_string(
                        row.get(
                            customer_col
                        )
                    )
                    if customer_col
                    else ""
                ),
                "card_id": (
                    safe_string(
                        row.get(
                            card_col
                        )
                    )
                    if card_col
                    else ""
                ),
            })

        fallback.sort(
            key=lambda item: item.get(
                "case_id",
                "",
            )
        )

        top_cases = fallback[:20]

    return {
        "confirmed_fraud_cases": confirmed_fraud_cases,
        "cleared_cases": cleared_cases,
        "cases": top_cases,
        "direct_history_cases": direct_history_cases[:20],
        "pattern_hint": pattern_hint,
    }


# ============================================================
# CROSS CUSTOMER ANALYSIS
# ============================================================

def analyze_cross_customer_activity(
    flagged_txn,
    transaction_index,
):
    """
    Analyze transactions from OTHER customers in the same region
    within +/-24 hours.

    Uses region_index when available.
    """

    flagged_time = safe_datetime(
        flagged_txn.get("ts")
    )

    if pd.isna(flagged_time):
        return {
            "other_customers": 0,
            "transactions": 0,
            "high_risk_other_customer_transactions": 0,
            "shared_device": False,
            "shared_email": False,
            "connected_card": False,
        }

    flagged_customer = safe_string(
        flagged_txn.get("customer_id")
    )

    flagged_region = safe_string(
        flagged_txn.get("addr1")
    )

    region_index = transaction_index.get(
        "region_index",
        {}
    )

    transaction_lookup = transaction_index.get(
        "transaction_index",
        {}
    )

    candidate_ids = region_index.get(
        flagged_region,
        []
    )

    if not candidate_ids:
        return {
            "other_customers": 0,
            "transactions": 0,
            "high_risk_other_customer_transactions": 0,
            "shared_device": False,
            "shared_email": False,
            "connected_card": False,
        }

    other_customers = set()
    total = 0
    high_risk = 0

    for txn_id in candidate_ids:

        txn = transaction_lookup.get(
            str(txn_id)
        )

        if txn is None:
            continue

        txn_customer = safe_string(
            txn.get("customer_id")
        )

        if (
            flagged_customer
            and txn_customer == flagged_customer
        ):
            continue

        txn_time = safe_datetime(
            txn.get("ts")
        )

        if pd.isna(txn_time):
            continue

        delta_hours = abs(
            (
                txn_time
                - flagged_time
            ).total_seconds()
        ) / 3600

        if delta_hours > 24:
            continue

        total += 1

        if txn_customer:
            other_customers.add(
                txn_customer
            )

        risk_score = safe_float(
            txn.get("risk_score")
        )

        if risk_score >= 0.70:
            high_risk += 1

    return {
        "other_customers": len(
            other_customers
        ),
        "transactions": total,
        "high_risk_other_customer_transactions": high_risk,
        "shared_device": False,
        "shared_email": False,
        "connected_card": False,
    }


# ============================================================
# SIMILAR AMOUNT ANALYSIS
# ============================================================

def analyze_similar_amount_activity(
    flagged_txn,
    transaction_index,
):
    """
    Find activity with similar transaction amounts within
    +/-24 hours.

    This is contextual evidence only.
    """

    flagged_amount = safe_float(
        flagged_txn.get(
            "TransactionAmt"
        )
    )

    flagged_time = safe_datetime(
        flagged_txn.get(
            "ts"
        )
    )

    flagged_customer = safe_string(
        flagged_txn.get(
            "customer_id"
        )
    )

    if (
        flagged_amount <= 0
        or pd.isna(flagged_time)
    ):
        return {
            "transactions": 0,
            "other_customers": 0,
            "high_risk": 0,
        }

    transaction_lookup = transaction_index.get(
        "transaction_index",
        {}
    )

    lower = flagged_amount * 0.90
    upper = flagged_amount * 1.10

    total = 0
    other_customers = set()
    high_risk = 0

    for txn in transaction_lookup.values():

        amount = safe_float(
            txn.get(
                "TransactionAmt"
            )
        )

        if (
            amount < lower
            or amount > upper
        ):
            continue

        txn_time = safe_datetime(
            txn.get(
                "ts"
            )
        )

        if pd.isna(txn_time):
            continue

        delta_hours = abs(
            (
                txn_time
                - flagged_time
            ).total_seconds()
        ) / 3600

        if delta_hours > 24:
            continue

        txn_id = safe_string(
            txn.get(
                "TransactionID"
            )
        )

        flagged_id = safe_string(
            flagged_txn.get(
                "TransactionID"
            )
        )

        if txn_id == flagged_id:
            continue

        total += 1

        txn_customer = safe_string(
            txn.get(
                "customer_id"
            )
        )

        if (
            txn_customer
            and txn_customer != flagged_customer
        ):
            other_customers.add(
                txn_customer
            )

        if safe_float(
            txn.get(
                "risk_score"
            )
        ) >= 0.70:
            high_risk += 1

    return {
        "transactions": total,
        "other_customers": len(
            other_customers
        ),
        "high_risk": high_risk,
    }


# ============================================================
# TEMPORARY INITIAL FRAUD PROBABILITY
# ============================================================

def estimate_initial_fraud_probability(
    case,
    flagged_txn,
    customer_history,
    region_info,
    identity_info,
    prior_info,
):
    """
    Temporary local heuristic.

    IMPORTANT:
    This is not a calibrated ML probability.
    """

    risk_score = safe_float(
        flagged_txn.get(
            "risk_score",
            case.get(
                "risk_score",
                0.50,
            ),
        ),
        0.50,
    )

    probability = risk_score

    if region_info.get(
        "new_region"
    ):
        probability += 0.05

    if customer_history.get(
        "unusual_amount",
        False,
    ):
        probability += 0.05

    if identity_info.get(
        "new_identity",
        False,
    ):
        probability += 0.05

    if identity_info.get(
        "proxy",
        False,
    ):
        probability += 0.05

    if prior_info.get(
        "confirmed_fraud_cases",
        0,
    ) >= 3:
        probability += 0.05

    return round(
        max(
            0.01,
            min(
                0.99,
                probability,
            ),
        ),
        3,
    )


# ============================================================
# INVESTIGATION
# ============================================================

def investigate(
    case_id,
):
    start_time = time.perf_counter()

    print(
        "\n"
        "============================================================"
    )
    print(
        f" FRAUD INVESTIGATION: {case_id}"
    )
    print(
        "============================================================"
    )

    # --------------------------------------------------------
    # Load case
    # --------------------------------------------------------

    print(
        "[1/10] Loading case..."
    )

    case = load_case(
        case_id
    )

    print(
        f"       Customer : {safe_string(case.get('customer_id'))}"
    )

    print(
        f"       Card     : {safe_string(case.get('card_id'))}"
    )

    print(
        f"       Flagged  : {safe_string(case.get('flagged_txn_id'))}"
    )

    # --------------------------------------------------------
    # Load transaction index
    # --------------------------------------------------------

    print(
        "[2/10] Loading transaction index..."
    )

    transaction_index = load_transaction_index()

    print(
        f"       Transactions indexed: "
        f"{len(transaction_index.get('transaction_index', {})):,}"
    )

    # --------------------------------------------------------
    # Flagged transaction
    # --------------------------------------------------------

    print(
        "[3/10] Retrieving flagged transaction..."
    )

    flagged_txn = get_flagged_transaction(
        case,
        transaction_index,
    )

    flagged_txn_id = safe_string(
        flagged_txn.get(
            "TransactionID"
        )
    )

    print(
        f"       Transaction {flagged_txn_id}"
    )

    print(
        f"       Amount: ${safe_float(flagged_txn.get('TransactionAmt')):.2f}"
    )

    print(
        f"       Risk  : {safe_float(flagged_txn.get('risk_score')):.2f}"
    )

    # --------------------------------------------------------
    # Customer transactions
    # --------------------------------------------------------

    print(
        "[4/10] Loading customer transaction history..."
    )

    customer_transactions = (
        load_customer_transactions(
            case.get("customer_id"),
            transaction_index,
        )
    )

    print(
        f"       Customer transactions: "
        f"{len(customer_transactions):,}"
    )

    # --------------------------------------------------------
    # Customer history
    # --------------------------------------------------------

    print(
        "[5/10] Analyzing customer behavior..."
    )

    customer_history = (
        analyze_customer_history(
            customer_transactions,
            flagged_txn,
        )
    )

    behavior_info = (
        analyze_transaction_behavior(
            flagged_txn,
            customer_transactions,
        )
    )

    time_info = (
        analyze_time_behavior(
            flagged_txn,
            customer_transactions,
        )
    )

    channel_info = (
        analyze_channel_behavior(
            flagged_txn,
            customer_transactions,
        )
    )

    region_info = (
        analyze_region_behavior(
            flagged_txn,
            customer_transactions,
        )
    )

    customer_history[
        "unusual_amount"
    ] = behavior_info.get(
        "unusual_amount",
        False,
    )

    print(
        f"       Average amount : "
        f"${customer_history.get('average_amount', 0):.2f}"
    )

    print(
        f"       Median amount  : "
        f"${customer_history.get('median_amount', 0):.2f}"
    )

    print(
        f"       Amount percentile: "
        f"{customer_history.get('flagged_amount_percentile', 0):.1f}%"
    )

    print(
        f"       Flagged channel: "
        f"{channel_info.get('flagged_channel', '')}"
    )

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    print(
        "[6/10] Loading identity/device evidence..."
    )

    identity_df = load_identity_for_transactions(
        [flagged_txn_id]
    )

    identity_info = extract_identity_info(
        identity_df,
        flagged_txn_id,
    )

    if identity_info.get(
        "available"
    ):
        print(
            "       Identity record found."
        )

        print(
            f"       New identity: "
            f"{identity_info.get('new_identity')}"
        )

        print(
            f"       Proxy: "
            f"{identity_info.get('proxy')}"
        )

        print(
            f"       Device: "
            f"{identity_info.get('device_info')}"
        )

    else:
        print(
            "       No identity record available."
        )

    # --------------------------------------------------------
    # Prior cases
    # --------------------------------------------------------

    print(
        "[7/10] Searching relevant closed cases..."
    )

    previous_cases = load_closed_cases()

    prior_info = analyze_prior_cases(
        case,
        flagged_txn,
        customer_transactions,
    )

    print(
        f"       Relevant historical cases: "
        f"{len(prior_info.get('cases', []))}"
    )

    print(
        f"       Direct confirmed fraud cases: "
        f"{prior_info.get('confirmed_fraud_cases', 0)}"
    )

    print(
        f"       Direct cleared cases: "
        f"{prior_info.get('cleared_cases', 0)}"
    )

    # --------------------------------------------------------
    # Cross customer
    # --------------------------------------------------------

    print(
        "[8/10] Checking cross-customer activity..."
    )

    cross_customer_info = (
        analyze_cross_customer_activity(
            flagged_txn,
            transaction_index,
        )
    )

    print(
        f"       Other customers in region/window: "
        f"{cross_customer_info.get('other_customers', 0)}"
    )

    print(
        f"       High-risk other-customer transactions: "
        f"{cross_customer_info.get('high_risk_other_customer_transactions', 0)}"
    )

    # --------------------------------------------------------
    # Similar amounts
    # --------------------------------------------------------

    print(
        "[9/10] Checking similar amount activity..."
    )

    similar_amount_info = (
        analyze_similar_amount_activity(
            flagged_txn,
            transaction_index,
        )
    )

    print(
        f"       Similar amount transactions: "
        f"{similar_amount_info.get('transactions', 0)}"
    )

    # --------------------------------------------------------
    # Initial probability
    # --------------------------------------------------------

    initial_probability = (
        estimate_initial_fraud_probability(
            case=case,
            flagged_txn=flagged_txn,
            customer_history=customer_history,
            region_info=region_info,
            identity_info=identity_info,
            prior_info=prior_info,
        )
    )

    case[
        "initial_fraud_probability"
    ] = initial_probability

    print(
        f"[10/10] Initial heuristic probability: "
        f"{initial_probability:.3f}"
    )

    # ========================================================
    # IMPORTANT TYPE FIX
    # ========================================================
    #
    # decision_engine.py expects customer_txns to be a pandas
    # DataFrame because it calls:
    #
    #     customer_txns.empty
    #
    # The investigation pipeline may return a list in some
    # versions. Normalize it here before crossing the boundary
    # into decision_engine.py.
    #

    if isinstance(
        customer_transactions,
        pd.DataFrame,
    ):
        customer_transactions_for_engine = (
            customer_transactions
        )
    else:
        customer_transactions_for_engine = (
            pd.DataFrame(
                customer_transactions
            )
        )

    # ========================================================
    # AMOUNT INFO
    # ========================================================

    amount_info = {
        "flagged_amount": behavior_info.get(
            "flagged_amount",
            0.0,
        ),
        "unusual_amount": behavior_info.get(
            "unusual_amount",
            False,
        ),
        "average_amount": customer_history.get(
            "average_amount",
            0.0,
        ),
        "median_amount": customer_history.get(
            "median_amount",
            0.0,
        ),
        "max_amount": customer_history.get(
            "max_amount",
            0.0,
        ),
        "flagged_amount_percentile": customer_history.get(
            "flagged_amount_percentile",
            0.0,
        ),
    }

    # ========================================================
    # DECISION ENGINE
    # ========================================================

    result = build_case_output(
        case=case,
        flagged_txn=flagged_txn,
        customer_txns=customer_transactions_for_engine,
        previous_cases=previous_cases,
        region_info=region_info,
        time_info=time_info,
        channel_info=channel_info,
        amount_info=amount_info,
        prior_info=prior_info,
        identity_df=identity_df,
        identity_info=identity_info,
        cross_customer_info=cross_customer_info,
        similar_amount_info=similar_amount_info,
        transaction_index=transaction_index,
    )

    # --------------------------------------------------------
    # Add metadata
    # --------------------------------------------------------

    latency = (
        time.perf_counter()
        - start_time
    )

    result[
        "latency_s"
    ] = round(
        latency,
        3,
    )

    result[
        "tokens"
    ] = {
        "input": 0,
        "output": 0,
        "total": 0,
        "note": (
            "Local prototype; no LLM token accounting yet."
        ),
    }

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    output_path = save_case(
        result,
        CASES_DIR,
    )

    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

    case_result = result.get(
        "case",
        {},
    )

    print(
        "\n"
        "============================================================"
    )

    print(
        " INVESTIGATION RESULT"
    )

    print(
        "============================================================"
    )

    print(
        f"Case              : "
        f"{result.get('case_id', '')}"
    )

    print(
        f"Status            : "
        f"{case_result.get('status', '')}"
    )

    print(
        f"Verdict           : "
        f"{case_result.get('verdict', '')}"
    )

    print(
        f"Fraud probability : "
        f"{case_result.get('fraud_probability', 0):.3f}"
    )

    print(
        f"Pattern           : "
        f"{case_result.get('pattern', '')}"
    )

    print(
        f"Exposure          : "
        f"${case_result.get('exposure_usd', 0):.2f}"
    )

    next_actions = result.get(
        "next_best_actions",
        {},
    )

    print(
        f"Primary action    : "
        f"{next_actions.get('primary_action', '')}"
    )

    print(
        f"Rules             : "
        f"{', '.join(next_actions.get('rules', []))}"
    )

    print(
        f"Stop reason       : "
        f"{result.get('stop_reason', '')}"
    )

    print(
        f"Saved to          : "
        f"{output_path}"
    )

    print(
        f"Latency           : "
        f"{result.get('latency_s', 0):.3f}s"
    )

    print(
        "============================================================"
    )

    return result


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Investigate an IEEE-CIS fraud case "
            "from the Hacker House Goa case pack."
        )
    )

    parser.add_argument(
        "--case",
        required=True,
        help=(
            "Case ID, for example HHG-001"
        ),
    )

    args = parser.parse_args()

    investigate(
        args.case
    )


if __name__ == "__main__":
    main()