import json
from pathlib import Path

import pandas as pd


# ============================================================
# POLICY ACTIONS
# ============================================================

AUTO_APPROVED_ACTIONS = {
    "ALLOW_TRANSACTION",
    "MONITOR_CARD",
    "MONITOR_CONNECTED_CARDS",
    "WARN_CUSTOMER",
    "VERIFY_WITH_CUSTOMER",
    "STEP_UP_AUTH",
    "GENERATE_REPORT",
    "CREATE_CASE",
    "ESCALATE_TO_ANALYST",
    "CLOSE_NO_FRAUD",
}

L1_ACTIONS = {
    "DECLINE_TRANSACTION",
    "BLOCK_CARD",
}

L2_ACTIONS = {
    "BLOCK_ALL_CARDS",
    "FILE_REPORT",
}


# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        result = float(value)

        if pd.isna(result):
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

    return str(value)


def normalize_text(value):
    return safe_string(value).strip().lower()


def unique_non_empty(values):
    result = []

    for value in values or []:

        value = safe_string(value).strip()

        if not value:
            continue

        if value.lower() == "nan":
            continue

        if value not in result:
            result.append(value)

    return result


# ============================================================
# PATTERN DETECTION
# ============================================================

def detect_card_testing(
    customer_txns,
    flagged_txn,
):
    """
    R5:
    3+ small online authorizations, often < $5,
    within approximately one hour, followed by a larger
    purchase.

    This is a supporting signal, not automatic proof.
    """

    if customer_txns is None or customer_txns.empty:
        return False

    if flagged_txn is None:
        return False

    flagged_time = pd.to_datetime(
        flagged_txn.get("ts"),
        errors="coerce",
    )

    if pd.isna(flagged_time):
        return False

    online = customer_txns.copy()

    if "channel" in online.columns:
        online = online[
            online["channel"]
            .astype(str)
            .str.lower()
            == "online"
        ]

    if online.empty:
        return False

    if "TransactionAmt" not in online.columns:
        return False

    if "ts" not in online.columns:
        return False

    online["amount_numeric"] = pd.to_numeric(
        online["TransactionAmt"],
        errors="coerce",
    )

    online["time_numeric"] = pd.to_datetime(
        online["ts"],
        errors="coerce",
    )

    small = online[
        (online["amount_numeric"] < 5)
        & online["time_numeric"].notna()
    ]

    if small.empty:
        return False

    delta_hours = (
        (
            small["time_numeric"]
            - flagged_time
        )
        .abs()
        .dt.total_seconds()
        / 3600
    )

    small_nearby = small[
        delta_hours <= 1
    ]

    return len(small_nearby) >= 3


def detect_recurring_legitimate_pattern(
    customer_txns,
    flagged_txn,
):
    """
    Detect a repeated transaction pattern that may indicate
    legitimate recurring behavior.

    This should only become relevant when the customer disputes
    the transaction.
    """

    if customer_txns is None or customer_txns.empty:
        return False

    if flagged_txn is None:
        return False

    region = safe_string(
        flagged_txn.get("addr1")
    )

    channel = normalize_text(
        flagged_txn.get("channel")
    )

    amount = safe_float(
        flagged_txn.get("TransactionAmt")
    )

    if amount <= 0:
        return False

    working = customer_txns.copy()

    if "addr1" in working.columns:
        working = working[
            working["addr1"]
            .astype(str)
            == region
        ]

    if "channel" in working.columns:
        working = working[
            working["channel"]
            .astype(str)
            .str.lower()
            == channel
        ]

    if "TransactionAmt" not in working.columns:
        return False

    amounts = pd.to_numeric(
        working["TransactionAmt"],
        errors="coerce",
    )

    lower = amount * 0.90
    upper = amount * 1.10

    matching = working[
        amounts.between(
            lower,
            upper,
            inclusive="both",
        )
    ]

    return len(matching) >= 3


# ============================================================
# IDENTITY / DEVICE ANALYSIS
# ============================================================

def analyze_identity_evidence(
    identity_info,
    channel_info,
):
    """
    Convert identity evidence into decision signals.

    Important:
    - New identity alone is NOT proof of fraud.
    - Proxy alone is NOT proof of fraud.
    - These signals become stronger when combined with
      online activity, unusual behavior, or mixed-channel
      inconsistencies.
    """

    identity_info = identity_info or {}

    available = bool(
        identity_info.get("available", False)
    )

    new_identity = bool(
        identity_info.get("new_identity", False)
    )

    proxy = bool(
        identity_info.get("proxy", False)
    )

    device_info = safe_string(
        identity_info.get("device_info")
    )

    device_type = safe_string(
        identity_info.get("device_type")
    )

    browser = safe_string(
        identity_info.get("browser")
    )

    operating_system = safe_string(
        identity_info.get("os")
    )

    screen = safe_string(
        identity_info.get("screen")
    )

    match_status = safe_string(
        identity_info.get("match_status")
    )

    anomalies = unique_non_empty(
        identity_info.get(
            "identity_anomalies",
            [],
        )
    )

    online_count = safe_float(
        channel_info.get("online_count", 0)
    )

    in_person_count = safe_float(
        channel_info.get("in_person_count", 0)
    )

    mixed_channel = (
        online_count > 0
        and in_person_count > 0
    )

    device_profiles = unique_non_empty(
        identity_info.get(
            "device_profiles",
            [],
        )
    )

    return {
        "available": available,
        "new_identity": new_identity,
        "proxy": proxy,
        "device_info": device_info,
        "device_type": device_type,
        "browser": browser,
        "operating_system": operating_system,
        "screen": screen,
        "match_status": match_status,
        "identity_anomalies": anomalies,
        "mixed_channel": mixed_channel,
        "device_profiles": device_profiles,
    }


def detect_card_not_present_new_device(
    flagged_txn,
    channel_info,
    identity_signals,
    amount_info,
):
    """
    Pattern:
    card-not-present / online transaction +
    new identity/device evidence.

    This is stronger when the transaction amount is also unusual,
    but a new device is not by itself proof of fraud.
    """

    if flagged_txn is None:
        return False

    channel = normalize_text(
        flagged_txn.get("channel")
    )

    online = (
        channel == "online"
        or safe_float(
            channel_info.get("online_count", 0)
        ) > 0
    )

    if not online:
        return False

    if not identity_signals.get("available"):
        return False

    new_identity = identity_signals.get(
        "new_identity",
        False,
    )

    proxy = identity_signals.get(
        "proxy",
        False,
    )

    unusual_amount = amount_info.get(
        "unusual_amount",
        False,
    )

    return (
        new_identity
        or (
            proxy
            and unusual_amount
        )
    )


def detect_account_takeover(
    flagged_txn,
    channel_info,
    identity_signals,
    amount_info,
    time_info,
):
    """
    Conservative account-takeover signal.

    Requires multiple behavioral indicators rather than a single
    identity field.

    Possible evidence:
    - online transaction
    - mixed channel history
    - new identity
    - proxy
    - identity anomaly
    - unusual amount
    - burst activity
    """

    if flagged_txn is None:
        return False

    if not identity_signals.get("available"):
        return False

    channel = normalize_text(
        flagged_txn.get("channel")
    )

    online = (
        channel == "online"
        or safe_float(
            channel_info.get("online_count", 0)
        ) > 0
    )

    if not online:
        return False

    signals = 0

    if identity_signals.get("new_identity"):
        signals += 1

    if identity_signals.get("proxy"):
        signals += 1

    if identity_signals.get(
        "identity_anomalies"
    ):
        signals += 1

    if identity_signals.get("mixed_channel"):
        signals += 1

    if amount_info.get("unusual_amount"):
        signals += 1

    if safe_float(
        time_info.get("transactions_1h", 0)
    ) >= 3:
        signals += 1

    return signals >= 2


# ============================================================
# EXPOSURE
# ============================================================

def calculate_exposure(
    affected_txn_ids,
    transaction_index,
):
    """
    Exposure = sum of absolute amounts of affected transactions.
    """

    exposure = 0.0

    for txn_id in affected_txn_ids:

        txn = transaction_index.get(
            str(txn_id)
        )

        if txn is None:
            continue

        amount = safe_float(
            txn.get("TransactionAmt")
        )

        exposure += abs(amount)

    return round(
        exposure,
        2,
    )


# ============================================================
# SHARED ORIGIN
# ============================================================

def detect_shared_origin(
    identity_signals,
    cross_customer_info,
):
    """
    Detect whether there is meaningful evidence that activity
    is connected across customers.

    IMPORTANT:
    Same region alone is NOT sufficient for R6.

    We require a device/identity signal or another explicit
    shared-origin indicator.
    """

    if identity_signals is None:
        return False

    device_profiles = identity_signals.get(
        "device_profiles",
        [],
    )

    other_customers = safe_float(
        cross_customer_info.get(
            "other_customers",
            0,
        )
    )

    # Local prototype currently has no graph-level shared-device
    # relationship. Therefore we do not claim R6 merely because
    # multiple customers used the same region.
    #
    # If a future graph query identifies the same device across
    # customers, this function can be expanded to use it.

    explicit_shared_device = bool(
        cross_customer_info.get(
            "shared_device",
            False,
        )
    )

    explicit_shared_email = bool(
        cross_customer_info.get(
            "shared_email",
            False,
        )
    )

    explicit_connected_card = bool(
        cross_customer_info.get(
            "connected_card",
            False,
        )
    )

    return (
        (
            len(device_profiles) > 0
            and other_customers > 0
            and explicit_shared_device
        )
        or explicit_shared_email
        or explicit_connected_card
    )


# ============================================================
# HIGH-RISK CROSS-CUSTOMER SIGNAL
# ============================================================

def count_high_risk_cross_customer(
    cross_customer_info,
):
    """
    Risk score is treated as a signal, NOT a fraud verdict.
    """

    return int(
        safe_float(
            cross_customer_info.get(
                "high_risk_other_customer_transactions",
                0,
            )
        )
    )


# ============================================================
# PATTERN DETERMINATION
# ============================================================

def determine_pattern(
    flagged_txn,
    channel_info,
    identity_signals,
    amount_info,
    time_info,
    region_info,
    card_testing,
    account_takeover,
    new_device,
):
    """
    Determine the strongest documented pattern.

    Order matters because some patterns are more specific than
    broad card-not-present behavior.
    """

    channel = normalize_text(
        flagged_txn.get("channel")
    )

    if card_testing:
        return "card_testing"

    if account_takeover:
        return "account_takeover"

    if new_device:
        return "card_not_present_new_device"

    if (
        channel == "online"
        and (
            amount_info.get("unusual_amount")
            or safe_float(
                time_info.get(
                    "transactions_48h",
                    0,
                )
            ) >= 4
        )
    ):
        return "card_not_present_fraud"

    if region_info.get("new_region"):

        if (
            channel == "in_person"
            and safe_float(
                time_info.get(
                    "transactions_24h",
                    0,
                )
            ) >= 2
        ):
            return "out_of_region_use"

    return "none"


# ============================================================
# FRAUD PROBABILITY
# ============================================================

def adjust_probability(
    initial_probability,
    pattern,
    region_info,
    amount_info,
    identity_signals,
    prior_info,
    cross_customer_info,
):
    """
    Temporary heuristic adjustment.

    This is explicitly NOT a calibrated probability model.
    """

    probability = safe_float(
        initial_probability,
        0.50,
    )

    if pattern == "card_testing":
        probability += 0.10

    elif pattern == "card_not_present_new_device":
        probability += 0.08

    elif pattern == "account_takeover":
        probability += 0.10

    elif pattern == "card_not_present_fraud":
        probability += 0.07

    elif pattern == "out_of_region_use":
        probability += 0.05

    if amount_info.get("unusual_amount"):
        probability += 0.03

    if identity_signals.get("proxy"):
        probability += 0.03

    if identity_signals.get("new_identity"):
        probability += 0.03

    if region_info.get("new_region"):
        probability += 0.02

    if prior_info.get(
        "confirmed_fraud_cases",
        0,
    ) >= 3:
        probability += 0.03

    # Do NOT increase probability merely because another
    # customer's risk_score is high. Risk score is not verdict.
    high_risk_count = count_high_risk_cross_customer(
        cross_customer_info
    )

    if high_risk_count >= 3:
        probability += 0.02

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
# SAR
# ============================================================

def determine_sar(
    fraud_probability,
    verdict,
    exposure,
    shared_origin,
    other_customer_fraud,
    coordinated_abuse,
):
    """
    SAR rule:

    FILE_REPORT when confirmed/strongly suspected AND at least
    one of:

    - exposure > $1,000
    - shared device/region/other customer fraud
    - coordinated/undocumented abuse
    """

    strongly_suspected = (
        verdict == "fraud"
        or fraud_probability >= 0.85
    )

    if not strongly_suspected:
        return {
            "required": False,
            "reason": (
                "Current evidence does not meet the threshold "
                "for filing a SAR."
            ),
            "narrative": "",
            "subjects": [],
            "total_amount_usd": 0,
            "activity_dates": [],
        }

    trigger = (
        exposure > 1000
        or shared_origin
        or other_customer_fraud
        or coordinated_abuse
    )

    if not trigger:
        return {
            "required": False,
            "reason": (
                "Fraud is strongly suspected, but the available "
                "evidence does not meet an additional SAR reporting "
                "condition such as exposure above $1,000, shared "
                "origin, other-customer fraud, or coordinated abuse."
            ),
            "narrative": "",
            "subjects": [],
            "total_amount_usd": 0,
            "activity_dates": [],
        }

    return {
        "required": True,
        "reason": (
            "Strong fraud evidence is present and at least one "
            "additional SAR reporting condition has been met."
        ),
        "narrative": (
            "Potential suspicious activity identified based on "
            "the documented investigation evidence and policy "
            "thresholds."
        ),
        "subjects": [],
        "total_amount_usd": round(
            exposure,
            2,
        ),
        "activity_dates": [],
    }


# ============================================================
# ACTION ENGINE
# ============================================================

def determine_actions(
    fraud_probability,
    verdict,
    exposure,
    pattern,
    shared_origin,
    coordinated_abuse,
    customer_dispute=False,
    customer_confirmed=False,
    customer_no_reply=False,
    recurring_legitimate_pattern=False,
    purchase_already_cleared=False,
    evidence_conflict=False,
    multiple_confirmed_customer_cards=False,
    credentials_confirmed_compromised=False,
):
    """
    Apply policy rules R1-R10.

    The engine recommends actions. Approval level is included
    separately.
    """

    actions = []
    rules = []

    def add_action(
        action,
        rule,
        reason,
    ):
        actions.append({
            "action": action,
            "approval": (
                "auto"
                if action in AUTO_APPROVED_ACTIONS
                else (
                    "L1"
                    if action in L1_ACTIONS
                    else "L2"
                )
            ),
            "rule": rule,
            "reason": reason,
        })

        rules.append(rule)

    # --------------------------------------------------------
    # R3
    # --------------------------------------------------------

    if customer_confirmed:

        add_action(
            "CLOSE_NO_FRAUD",
            "R3",
            "Customer confirmed the transaction as legitimate.",
        )

        return actions, rules

    # --------------------------------------------------------
    # R2
    # --------------------------------------------------------

    if customer_dispute:

        add_action(
            "BLOCK_CARD",
            "R2",
            "Customer disputed the transaction; block the affected card.",
        )

        add_action(
            "CREATE_CASE",
            "R2",
            "Customer dispute requires an investigation case.",
        )

        if (
            exposure > 1000
            or shared_origin
        ):
            add_action(
                "FILE_REPORT",
                "R2",
                "Disputed activity meets the additional reporting condition.",
            )

        return actions, rules

    # --------------------------------------------------------
    # R9
    # --------------------------------------------------------

    if coordinated_abuse:

        add_action(
            "CREATE_CASE",
            "R9",
            "Repeated or coordinated abuse across customers requires a case.",
        )

        add_action(
            "FILE_REPORT",
            "R9",
            "Coordinated or undocumented abuse requires reporting.",
        )

        add_action(
            "ESCALATE_TO_ANALYST",
            "R9",
            "Undocumented/coordinated activity requires analyst review.",
        )

        return actions, rules

    # --------------------------------------------------------
    # R10
    # --------------------------------------------------------

    if (
        multiple_confirmed_customer_cards
        or credentials_confirmed_compromised
    ):

        add_action(
            "BLOCK_ALL_CARDS",
            "R10",
            "At least two customer cards show confirmed fraud or credentials are confirmed compromised.",
        )

        add_action(
            "CREATE_CASE",
            "R10",
            "Customer-wide compromise requires a case.",
        )

        return actions, rules

    # --------------------------------------------------------
    # R5
    # --------------------------------------------------------

    if pattern == "card_testing":

        add_action(
            "DECLINE_TRANSACTION",
            "R5",
            "Card-testing behavior requires declining the transaction.",
        )

        add_action(
            "STEP_UP_AUTH",
            "R5",
            "Card-testing behavior requires stronger authentication.",
        )

        if purchase_already_cleared:
            add_action(
                "BLOCK_CARD",
                "R5",
                "A larger purchase has already cleared following card-testing activity.",
            )

        return actions, rules

    # --------------------------------------------------------
    # R6
    # --------------------------------------------------------

    if shared_origin:

        add_action(
            "CREATE_CASE",
            "R6",
            "Shared origin across affected cards requires a case.",
        )

        add_action(
            "FILE_REPORT",
            "R6",
            "Shared origin with fraud evidence meets the reporting condition.",
        )

        add_action(
            "MONITOR_CONNECTED_CARDS",
            "R6",
            "Connected cards should be monitored.",
        )

        return actions, rules

    # --------------------------------------------------------
    # R7
    # --------------------------------------------------------

    if (
        recurring_legitimate_pattern
        and customer_dispute
    ):

        add_action(
            "CREATE_CASE",
            "R7",
            "Recurring disputed activity should be documented.",
        )

        add_action(
            "VERIFY_WITH_CUSTOMER",
            "R7",
            "Customer verification is required before taking stronger action.",
        )

        add_action(
            "WARN_CUSTOMER",
            "R7",
            "Customer should be warned about the activity.",
        )

        return actions, rules

    # --------------------------------------------------------
    # R4
    # --------------------------------------------------------

    if customer_no_reply:

        add_action(
            "MONITOR_CARD",
            "R4",
            "No customer response within the verification window.",
        )

        add_action(
            "DECLINE_TRANSACTION",
            "R4",
            "Pending authorization should be declined while verification remains unresolved.",
        )

        if exposure > 500:

            add_action(
                "ESCALATE_TO_ANALYST",
                "R4",
                "Exposure exceeds $500 without customer response.",
            )

        return actions, rules

    # --------------------------------------------------------
    # R8
    # --------------------------------------------------------

    if (
        evidence_conflict
        or exposure > 500
    ):

        add_action(
            "ESCALATE_TO_ANALYST",
            "R8",
            "Evidence conflict or exposure above $500 requires analyst review.",
        )

        add_action(
            "CREATE_CASE",
            "R8",
            "The investigation requires documented follow-up.",
        )

        return actions, rules

    # --------------------------------------------------------
    # R1
    # --------------------------------------------------------

    if fraud_probability < 0.70:

        add_action(
            "VERIFY_WITH_CUSTOMER",
            "R1",
            "Evidence is not strong enough for immediate blocking.",
        )

        add_action(
            "CREATE_CASE",
            "R1",
            "Weak fraud signal should be documented.",
        )

        return actions, rules

    # --------------------------------------------------------
    # Stronger but unresolved signal
    # --------------------------------------------------------

    add_action(
        "STEP_UP_AUTH",
        "R1",
        "Additional authentication is appropriate before stronger action.",
    )

    add_action(
        "CREATE_CASE",
        "R1",
        "Elevated fraud signal requires investigation tracking.",
    )

    return actions, rules


# ============================================================
# NEXT BEST ACTION OBJECT
# ============================================================

def build_next_best_actions(
    actions,
    rules,
):
    """
    Convert the internal action list into the README/validator
    compatible next_best_actions object.

    The detailed action records are preserved under "actions".
    """

    if not actions:
        return {
            "primary_action": "",
            "actions": [],
            "rules": unique_non_empty(rules),
            "approval_required": False,
        }

    primary = actions[0]

    approval_levels = unique_non_empty(
        [
            action.get("approval", "")
            for action in actions
        ]
    )

    approval_required = any(
        level in {"L1", "L2"}
        for level in approval_levels
    )

    return {
        "primary_action": primary.get(
            "action",
            "",
        ),
        "actions": actions,
        "rules": unique_non_empty(rules),
        "approval_required": approval_required,
    }


# ============================================================
# STATUS / VERDICT
# ============================================================

def determine_status_verdict(
    fraud_probability,
    customer_confirmed=False,
    customer_dispute=False,
    evidence_settled=False,
):
    if customer_confirmed:
        return "closed_legitimate", "legitimate"

    if customer_dispute:
        return "open", "uncertain"

    if evidence_settled:

        if fraud_probability >= 0.85:
            return "closed_fraud", "fraud"

        if fraud_probability <= 0.15:
            return "closed_legitimate", "legitimate"

    if fraud_probability >= 0.85:
        return "open", "fraud"

    if fraud_probability <= 0.15:
        return "open", "legitimate"

    return "open", "uncertain"


# ============================================================
# STOP REASON
# ============================================================

def determine_stop_reason(
    fraud_probability,
    independent_evidence_count,
    customer_confirmed=False,
    customer_dispute=False,
    evidence_conflict=False,
):
    if customer_confirmed:
        return "Customer verification settled the decision."

    if customer_dispute:
        return "Customer dispute requires policy-driven follow-up."

    if evidence_conflict:
        return "Conflicting evidence requires analyst review."

    if (
        fraud_probability >= 0.85
        and independent_evidence_count >= 2
    ):
        return (
            "Fraud probability reached the strong-evidence threshold "
            "with at least two independent supporting signals."
        )

    if (
        fraud_probability <= 0.15
        and independent_evidence_count >= 2
    ):
        return (
            "Fraud probability reached the low-risk threshold "
            "with at least two independent supporting signals."
        )

    return (
        "Further verification or evidence could materially change "
        "the decision."
    )


# ============================================================
# BUILD EVIDENCE
# ============================================================

def build_evidence(
    flagged_txn,
    pattern,
    fraud_probability,
    region_info,
    amount_info,
    prior_info,
    identity_signals,
    cross_customer_info,
):
    evidence = []

    txn_id = safe_string(
        flagged_txn.get("TransactionID")
    )

    risk_score = safe_float(
        flagged_txn.get("risk_score")
    )

    evidence.append({
        "claim": (
            f"Transaction {txn_id} has a risk score of "
            f"{risk_score:.2f}."
        ),
        "source": "transactions.csv",
        "ref": txn_id,
        "entity_ids": [txn_id],
    })

    if region_info.get("new_region"):

        evidence.append({
            "claim": (
                "The flagged transaction occurred in a region "
                "not previously observed in the customer's transaction history."
            ),
            "source": "customer transaction history",
            "ref": safe_string(
                region_info.get("flagged_region")
            ),
            "entity_ids": [txn_id],
        })

    else:

        evidence.append({
            "claim": (
                "The flagged transaction's region is present "
                "in the customer's historical activity."
            ),
            "source": "customer transaction history",
            "ref": safe_string(
                region_info.get("flagged_region")
            ),
            "entity_ids": [txn_id],
        })

    if amount_info.get("unusual_amount"):

        evidence.append({
            "claim": (
                "The transaction amount is unusually high or low "
                "relative to this customer's historical amounts."
            ),
            "source": "customer transaction history",
            "ref": txn_id,
            "entity_ids": [txn_id],
        })

    if prior_info.get("confirmed_fraud_cases", 0) > 0:

        evidence.append({
            "claim": (
                f"The available history contains "
                f"{prior_info.get('confirmed_fraud_cases')} "
                f"prior confirmed-fraud case(s)."
            ),
            "source": "closed_cases_history.csv",
            "ref": "prior_cases",
            "entity_ids": [],
        })

    if identity_signals.get("new_identity"):

        evidence.append({
            "claim": (
                "Identity data marks the transaction identity as New."
            ),
            "source": "identity.csv",
            "ref": txn_id,
            "entity_ids": [txn_id],
        })

    if identity_signals.get("proxy"):

        evidence.append({
            "claim": (
                "Identity data contains a proxy indicator."
            ),
            "source": "identity.csv",
            "ref": txn_id,
            "entity_ids": [txn_id],
        })

    if identity_signals.get("device_profiles"):

        evidence.append({
            "claim": (
                "Identity/device information is available for the "
                "flagged transaction."
            ),
            "source": "identity.csv",
            "ref": txn_id,
            "entity_ids": [
                safe_string(
                    identity_signals.get(
                        "device_info"
                    )
                )
            ],
        })

    other_customers = int(
        safe_float(
            cross_customer_info.get(
                "other_customers",
                0,
            )
        )
    )

    if other_customers > 0:

        evidence.append({
            "claim": (
                f"{other_customers} other customer(s) had activity "
                "in the same region within the analysis window."
            ),
            "source": "transaction index",
            "ref": safe_string(
                region_info.get("flagged_region")
            ),
            "entity_ids": [txn_id],
        })

    evidence.append({
        "claim": (
            f"Detected investigation pattern: {pattern}."
        ),
        "source": "local decision engine",
        "ref": pattern,
        "entity_ids": [txn_id],
    })

    evidence.append({
        "claim": (
            f"Temporary heuristic fraud probability is "
            f"{fraud_probability:.3f}; this is not a calibrated "
            "machine-learning probability."
        ),
        "source": "local decision engine",
        "ref": txn_id,
        "entity_ids": [txn_id],
    })

    return evidence


# ============================================================
# MAIN CASE BUILDER
# ============================================================

def build_case_output(
    case,
    flagged_txn,
    customer_txns,
    previous_cases,
    region_info,
    time_info,
    channel_info,
    amount_info,
    prior_info,
    identity_df=None,
    identity_info=None,
    cross_customer_info=None,
    similar_amount_info=None,
    transaction_index=None,
):
    """
    Build the complete README-compatible case JSON.
    """

    identity_info = identity_info or {}

    cross_customer_info = (
        cross_customer_info or {}
    )

    similar_amount_info = (
        similar_amount_info or {}
    )

    transaction_index = (
        transaction_index or {}
    )

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    identity_signals = analyze_identity_evidence(
        identity_info,
        channel_info,
    )

    # --------------------------------------------------------
    # Pattern signals
    # --------------------------------------------------------

    card_testing = detect_card_testing(
        customer_txns,
        flagged_txn,
    )

    recurring_legitimate_pattern = (
        detect_recurring_legitimate_pattern(
            customer_txns,
            flagged_txn,
        )
    )

    new_device_pattern = (
        detect_card_not_present_new_device(
            flagged_txn,
            channel_info,
            identity_signals,
            amount_info,
        )
    )

    account_takeover = detect_account_takeover(
        flagged_txn,
        channel_info,
        identity_signals,
        amount_info,
        time_info,
    )

    pattern = determine_pattern(
        flagged_txn,
        channel_info,
        identity_signals,
        amount_info,
        time_info,
        region_info,
        card_testing,
        account_takeover,
        new_device_pattern,
    )

    # --------------------------------------------------------
    # Probability
    # --------------------------------------------------------

    initial_probability = safe_float(
        case.get(
            "initial_fraud_probability",
            flagged_txn.get("risk_score", 0.50),
        ),
        0.50,
    )

    fraud_probability = adjust_probability(
        initial_probability,
        pattern,
        region_info,
        amount_info,
        identity_signals,
        prior_info,
        cross_customer_info,
    )

    # --------------------------------------------------------
    # Affected transactions
    # --------------------------------------------------------

    flagged_txn_id = safe_string(
        flagged_txn.get("TransactionID")
    )

    affected_txn_ids = [
        flagged_txn_id
    ]

    # --------------------------------------------------------
    # Exposure
    # --------------------------------------------------------

    exposure = calculate_exposure(
        affected_txn_ids,
        transaction_index,
    )

    # --------------------------------------------------------
    # Shared origin
    # --------------------------------------------------------

    shared_origin = detect_shared_origin(
        identity_signals,
        cross_customer_info,
    )

    # Risk scores from other customers are NOT treated as
    # confirmed fraud.
    other_customer_fraud = False

    # --------------------------------------------------------
    # Coordinated abuse
    # --------------------------------------------------------

    undocumented_coordinated_abuse = (
        pattern == "undocumented"
        and shared_origin
    )

    # --------------------------------------------------------
    # Evidence conflict
    # --------------------------------------------------------

    evidence_conflict = False

    if (
        fraud_probability >= 0.70
        and recurring_legitimate_pattern
        and region_info.get("known_region")
        and safe_float(
            time_info.get(
                "transactions_24h",
                0,
            )
        ) >= 3
        and safe_float(
            flagged_txn.get(
                "risk_score",
                0,
            )
        ) < 0.85
    ):
        evidence_conflict = True

    # --------------------------------------------------------
    # Independent evidence count
    # --------------------------------------------------------

    independent_evidence_count = 0

    risk_score = safe_float(
        flagged_txn.get("risk_score")
    )

    if risk_score >= 0.70:
        independent_evidence_count += 1

    if card_testing:
        independent_evidence_count += 1

    if new_device_pattern:
        independent_evidence_count += 1

    if account_takeover:
        independent_evidence_count += 1

    if region_info.get("new_region"):
        independent_evidence_count += 1

    if amount_info.get("unusual_amount"):
        independent_evidence_count += 1

    if identity_signals.get("proxy"):
        independent_evidence_count += 1

    if prior_info.get(
        "confirmed_fraud_cases",
        0,
    ) >= 2:
        independent_evidence_count += 1

    if shared_origin:
        independent_evidence_count += 1

    # --------------------------------------------------------
    # Simulated customer response
    # --------------------------------------------------------
    #
    # No customer response is actually available in this
    # local dataset. Therefore these remain False.
    # The evidence request is recorded instead.
    #

    customer_confirmed = False
    customer_dispute = False
    customer_no_reply = False

    # --------------------------------------------------------
    # Verdict/status
    # --------------------------------------------------------

    evidence_settled = (
        (
            fraud_probability >= 0.85
            or fraud_probability <= 0.15
        )
        and independent_evidence_count >= 2
    )

    status, verdict = determine_status_verdict(
        fraud_probability,
        customer_confirmed=customer_confirmed,
        customer_dispute=customer_dispute,
        evidence_settled=evidence_settled,
    )

    # --------------------------------------------------------
    # Card testing purchase check
    # --------------------------------------------------------

    purchase_already_cleared = False

    if card_testing:

        flagged_amount = safe_float(
            flagged_txn.get("TransactionAmt")
        )

        if flagged_amount > 100:
            purchase_already_cleared = True

    # --------------------------------------------------------
    # Multiple confirmed customer cards
    # --------------------------------------------------------

    multiple_confirmed_customer_cards = False

    # We do not infer this from transaction risk scores.
    # It requires confirmed historical fraud tied to multiple
    # customer cards, which the current local evidence does not
    # establish automatically.

    credentials_confirmed_compromised = False

    # --------------------------------------------------------
    # Actions
    # --------------------------------------------------------

    action_list, rules = determine_actions(
        fraud_probability=fraud_probability,
        verdict=verdict,
        exposure=exposure,
        pattern=pattern,
        shared_origin=shared_origin,
        coordinated_abuse=undocumented_coordinated_abuse,
        customer_dispute=customer_dispute,
        customer_confirmed=customer_confirmed,
        customer_no_reply=customer_no_reply,
        recurring_legitimate_pattern=(
            recurring_legitimate_pattern
        ),
        purchase_already_cleared=(
            purchase_already_cleared
        ),
        evidence_conflict=evidence_conflict,
        multiple_confirmed_customer_cards=(
            multiple_confirmed_customer_cards
        ),
        credentials_confirmed_compromised=(
            credentials_confirmed_compromised
        ),
    )

    # --------------------------------------------------------
    # Next Best Actions
    # --------------------------------------------------------

    next_best_actions = build_next_best_actions(
        action_list,
        rules,
    )

    # --------------------------------------------------------
    # Evidence requests
    # --------------------------------------------------------

    evidence_requests = []

    if not customer_confirmed:

        evidence_requests.append({
            "type": "customer_validation",
            "status": "requested",
            "assumption": (
                "No customer response is available in the local "
                "prototype, so customer validation is simulated "
                "as pending."
            ),
        })

    if card_testing:

        evidence_requests.append({
            "type": "step_up_auth",
            "status": "requested",
            "assumption": (
                "Step-up authentication response is unavailable "
                "in the local dataset."
            ),
        })

    if evidence_conflict:

        evidence_requests.append({
            "type": "analyst_info",
            "status": "requested",
            "assumption": (
                "Analyst review is required because available "
                "signals conflict."
            ),
        })

    # --------------------------------------------------------
    # Stop reason
    # --------------------------------------------------------

    stop_reason = determine_stop_reason(
        fraud_probability,
        independent_evidence_count,
        customer_confirmed=customer_confirmed,
        customer_dispute=customer_dispute,
        evidence_conflict=evidence_conflict,
    )

    # --------------------------------------------------------
    # SAR
    # --------------------------------------------------------

    sar = determine_sar(
        fraud_probability=fraud_probability,
        verdict=verdict,
        exposure=exposure,
        shared_origin=shared_origin,
        other_customer_fraud=other_customer_fraud,
        coordinated_abuse=undocumented_coordinated_abuse,
    )

    # --------------------------------------------------------
    # Evidence
    # --------------------------------------------------------

    evidence = build_evidence(
        flagged_txn=flagged_txn,
        pattern=pattern,
        fraud_probability=fraud_probability,
        region_info=region_info,
        amount_info=amount_info,
        prior_info=prior_info,
        identity_signals=identity_signals,
        cross_customer_info=cross_customer_info,
    )

    # --------------------------------------------------------
    # Similar prior cases
    # --------------------------------------------------------

    similar_prior_cases = []

    if prior_info:
        similar_prior_cases = (
            prior_info.get(
                "cases",
                [],
            )
        )

    # --------------------------------------------------------
    # Connected cards
    # --------------------------------------------------------

    connected_card_ids = []

    card_id = safe_string(
        case.get("card_id")
    )

    if card_id:
        connected_card_ids.append(
            card_id
        )

    # --------------------------------------------------------
    # Connected devices
    # --------------------------------------------------------

    connected_device_profiles = (
        identity_signals.get(
            "device_profiles",
            [],
        )
    )

    # --------------------------------------------------------
    # Pattern description
    # --------------------------------------------------------

    pattern_description = ""

    if pattern == "account_takeover":

        pattern_description = (
            "Online activity shows multiple identity or behavioral "
            "anomalies consistent with a possible account-takeover "
            "scenario. These signals require verification and are "
            "not treated as proof by themselves."
        )

    elif pattern == "card_not_present_new_device":

        pattern_description = (
            "An online transaction is associated with new identity "
            "or device evidence. This strengthens the card-not-present "
            "signal but does not independently establish fraud."
        )

    elif pattern == "card_testing":

        pattern_description = (
            "Multiple small online transactions occurred within a "
            "short time window, consistent with possible card testing."
        )

    elif pattern == "card_not_present_fraud":

        pattern_description = (
            "Online activity shows an unusual amount or burst "
            "pattern consistent with possible card-not-present fraud."
        )

    elif pattern == "out_of_region_use":

        pattern_description = (
            "The transaction occurred in a region not previously "
            "observed in the customer's history."
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary = (
        f"Transaction {flagged_txn_id} was investigated using "
        f"customer history, identity/device evidence, prior cases, "
        f"and cross-customer activity. "
        f"The detected pattern is {pattern}. "
        f"The temporary heuristic fraud probability is "
        f"{fraud_probability:.3f}. "
        f"The current recommendation follows "
        f"{', '.join(rules) if rules else 'the available evidence'}."
    )

    # --------------------------------------------------------
    # Final output
    # --------------------------------------------------------

    output = {
        "case_id": safe_string(
            case.get("case_id")
        ),

        "case": {
            "status": status,
            "verdict": verdict,
            "fraud_probability": fraud_probability,
            "pattern": pattern,
            "pattern_description": pattern_description,
            "affected_txn_ids": affected_txn_ids,
            "first_suspicious_txn_id": flagged_txn_id,
            "connected_card_ids": connected_card_ids,
            "connected_device_profiles": connected_device_profiles,
            "exposure_usd": exposure,
            "evidence": evidence,
            "similar_prior_cases": similar_prior_cases,
            "summary": summary,
            "written_to_graph": False,
            "graph_case_id": "",
        },

        "evidence_requests": evidence_requests,

        "next_best_actions": next_best_actions,

        "sar": sar,

        "stop_reason": stop_reason,

        "tool_calls": [
            {
                "tool": "transaction_index",
                "purpose": (
                    "Retrieve flagged and customer transaction history."
                ),
            },
            {
                "tool": "identity.csv",
                "purpose": (
                    "Retrieve identity and device evidence."
                ),
            },
            {
                "tool": "closed_cases_history.csv",
                "purpose": (
                    "Retrieve previous fraud/legitimate case evidence."
                ),
            },
        ],

        "tokens": {
            "input": 0,
            "output": 0,
            "total": 0,
            "note": (
                "Local prototype; no LLM token accounting yet."
            ),
        },

        "latency_s": 0.0,
    }

    return output


# ============================================================
# SAVE CASE
# ============================================================

def save_case(
    output,
    cases_dir,
):
    cases_dir = Path(cases_dir)

    cases_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    case_id = safe_string(
        output.get("case_id"),
        "UNKNOWN",
    )

    output_path = cases_dir / (
        f"{case_id}.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
            ensure_ascii=False,
        )

    return output_path