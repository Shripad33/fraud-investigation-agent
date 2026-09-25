import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CASES_DIR = BASE_DIR / "cases"


REQUIRED_TOP_LEVEL = {
    "case_id",
    "case",
    "evidence_requests",
    "next_best_actions",
    "sar",
    "stop_reason",
    "tool_calls",
    "tokens",
    "latency_s",
}

REQUIRED_CASE_FIELDS = {
    "status",
    "verdict",
    "fraud_probability",
    "pattern",
    "pattern_description",
    "affected_txn_ids",
    "first_suspicious_txn_id",
    "connected_card_ids",
    "connected_device_profiles",
    "exposure_usd",
    "evidence",
    "similar_prior_cases",
    "summary",
    "written_to_graph",
    "graph_case_id",
}

VALID_STATUS = {
    "open",
    "closed_fraud",
    "closed_legitimate",
    "escalated",
}

VALID_VERDICTS = {
    "fraud",
    "legitimate",
    "uncertain",
}

VALID_PATTERNS = {
    "card_testing",
    "card_not_present_fraud",
    "card_not_present_new_device",
    "out_of_region_use",
    "account_takeover",
    "undocumented",
    "none",
}


def validate_case(path):
    errors = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return [f"Invalid JSON: {e}"]

    # --------------------------------------------------
    # Top-level fields
    # --------------------------------------------------

    missing = REQUIRED_TOP_LEVEL - set(data.keys())

    for field in sorted(missing):
        errors.append(f"Missing top-level field: {field}")

    # --------------------------------------------------
    # Case fields
    # --------------------------------------------------

    case = data.get("case", {})

    missing_case = REQUIRED_CASE_FIELDS - set(case.keys())

    for field in sorted(missing_case):
        errors.append(f"Missing case field: {field}")

    # --------------------------------------------------
    # Enum validation
    # --------------------------------------------------

    if case.get("status") not in VALID_STATUS:
        errors.append(
            f"Invalid status: {case.get('status')}"
        )

    if case.get("verdict") not in VALID_VERDICTS:
        errors.append(
            f"Invalid verdict: {case.get('verdict')}"
        )

    if case.get("pattern") not in VALID_PATTERNS:
        errors.append(
            f"Invalid pattern: {case.get('pattern')}"
        )

    # --------------------------------------------------
    # Fraud probability
    # --------------------------------------------------

    probability = case.get("fraud_probability")

    if not isinstance(probability, (int, float)):
        errors.append("fraud_probability must be numeric")
    elif not 0 <= probability <= 1:
        errors.append(
            f"fraud_probability must be between 0 and 1: {probability}"
        )

    # --------------------------------------------------
    # Exposure
    # --------------------------------------------------

    exposure = case.get("exposure_usd")

    if not isinstance(exposure, (int, float)):
        errors.append("exposure_usd must be numeric")
    elif exposure < 0:
        errors.append(
            f"exposure_usd cannot be negative: {exposure}"
        )

    # --------------------------------------------------
    # Affected transactions
    # --------------------------------------------------

    affected = case.get("affected_txn_ids")

    if not isinstance(affected, list):
        errors.append("affected_txn_ids must be a list")

    # --------------------------------------------------
    # Evidence
    # --------------------------------------------------

    evidence = case.get("evidence")

    if not isinstance(evidence, list):
        errors.append("evidence must be a list")

    # --------------------------------------------------
    # Evidence requests
    # --------------------------------------------------

    evidence_requests = data.get("evidence_requests")

    if not isinstance(evidence_requests, list):
        errors.append("evidence_requests must be a list")

    # --------------------------------------------------
    # Actions
    # --------------------------------------------------

    actions = data.get("next_best_actions")

    if not isinstance(actions, dict):
        errors.append("next_best_actions must be an object")

    # --------------------------------------------------
    # SAR
    # --------------------------------------------------

    sar = data.get("sar")

    if not isinstance(sar, dict):
        errors.append("sar must be an object")
    else:
        required_sar = {
            "required",
            "reason",
            "narrative",
            "subjects",
            "total_amount_usd",
            "activity_dates",
        }

        for field in required_sar:
            if field not in sar:
                errors.append(
                    f"Missing SAR field: {field}"
                )

    # --------------------------------------------------
    # Graph
    # --------------------------------------------------

    if not isinstance(case.get("written_to_graph"), bool):
        errors.append(
            "written_to_graph must be true or false"
        )

    # --------------------------------------------------
    # Result
    # --------------------------------------------------

    if errors:
        return errors

    return []


def main():
    if len(sys.argv) > 1:
        paths = [
            CASES_DIR / f"{sys.argv[1]}.json"
        ]
    else:
        paths = sorted(CASES_DIR.glob("HHG-*.json"))

    if not paths:
        print("No case JSON files found.")
        sys.exit(1)

    total = 0
    failed = 0

    print("=" * 60)
    print("FRAUD CASE VALIDATION")
    print("=" * 60)

    for path in paths:
        total += 1

        errors = validate_case(path)

        if errors:
            failed += 1

            print(f"\n❌ {path.name}")

            for error in errors:
                print(f"   - {error}")

        else:
            print(f"✅ {path.name}")

    print("\n" + "=" * 60)
    print(f"Total cases : {total}")
    print(f"Passed      : {total - failed}")
    print(f"Failed      : {failed}")
    print("=" * 60)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()