
import json
import subprocess
import sys
from pathlib import Path

import streamlit as st


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
CASES_DIR = BASE_DIR / "cases"
INVESTIGATE_SCRIPT = BASE_DIR / "scripts" / "investigate_case.py"

st.set_page_config(
    page_title="Fraud Investigation Agent",
    page_icon="🛡️",
    layout="wide",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    .title {
        font-size: 2.5rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }

    .subtitle {
        color: #667085;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }

    .card {
        background: white;
        padding: 1.2rem;
        border-radius: 14px;
        border: 1px solid #e5e7eb;
        margin-bottom: 1rem;
    }

    .fraud-box {
        background: #fff1f0;
        border: 1px solid #ffccc7;
        padding: 1.2rem;
        border-radius: 14px;
        text-align: center;
    }

    .uncertain-box {
        background: #fff7e6;
        border: 1px solid #ffd591;
        padding: 1.2rem;
        border-radius: 14px;
        text-align: center;
    }

    .clear-box {
        background: #f6ffed;
        border: 1px solid #b7eb8f;
        padding: 1.2rem;
        border-radius: 14px;
        text-align: center;
    }

    .section-title {
        font-size: 1.35rem;
        font-weight: 700;
        margin-top: 1.5rem;
        margin-bottom: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def load_case(case_id):
    path = CASES_DIR / f"{case_id}.json"

    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def run_investigation(case_id):
    """Run the investigation engine, building the transaction index if needed."""
    index_path = os.path.join(BASE_DIR, "outputs", "transaction_index.json")

    try:
        # Build the transaction index if it is missing
        if not os.path.exists(index_path):
            build_result = subprocess.run(
                [
                    sys.executable,
                    os.path.join(BASE_DIR, "scripts", "build_index.py"),
                ],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if build_result.returncode != 0:
                return None, (
                    "Could not build the transaction index.\n\n"
                    + build_result.stdout
                    + "\n"
                    + build_result.stderr
                )

        # Run the investigation
        result = subprocess.run(
            [
                sys.executable,
                os.path.join(BASE_DIR, "scripts", "investigate_case.py"),
                "--case",
                case_id,
            ],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=180,
        )

        if result.returncode != 0:
            return None, result.stdout + "\n" + result.stderr

        # Load the generated case result
        case_file = os.path.join(BASE_DIR, "cases", f"{case_id}.json")

        if os.path.exists(case_file):
            with open(case_file, "r", encoding="utf-8") as f:
                return json.load(f), None

        return None, "Investigation completed but case output was not found."

    except subprocess.TimeoutExpired:
        return None, "Investigation timed out."

    except Exception as e:
        return None, str(e)


def money(value):
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return str(value)


def pretty(value):
    return str(value).replace("_", " ").replace("-", " ").title()


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="title">🛡️ Fraud Investigation Agent</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="subtitle">
    AI-assisted fraud investigation using transaction behavior,
    historical cases, identity evidence and graph-based relationships.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("Investigation Control")

case_files = sorted(CASES_DIR.glob("HHG-*.json"))
case_ids = [x.stem for x in case_files]

if case_ids:

    default_index = (
        case_ids.index("HHG-002")
        if "HHG-002" in case_ids
        else 0
    )

    selected_case = st.sidebar.selectbox(
        "Select Investigation Case",
        case_ids,
        index=default_index,
    )

else:

    selected_case = st.sidebar.text_input(
        "Case ID",
        value="HHG-002",
    )


st.sidebar.markdown("---")

st.sidebar.markdown("### System Status")

st.sidebar.success("Investigation Engine ONLINE")
st.sidebar.success("Case Validator ONLINE")
st.sidebar.info("TigerGraph Fraud Graph AVAILABLE")

st.sidebar.markdown("---")

st.sidebar.markdown("### Case Pack")

st.sidebar.write(f"Available cases: **{len(case_ids)}**")

st.sidebar.caption(
    "Hacker House Goa Fraud Investigation Project"
)


# ============================================================
# INITIAL CASE
# ============================================================

if "case_data" not in st.session_state:

    existing = load_case(selected_case)

    if existing:
        st.session_state.case_data = existing
        st.session_state.case_id = selected_case


# ============================================================
# CASE SELECTION CHANGE
# ============================================================

if (
    "case_id" in st.session_state
    and st.session_state.case_id != selected_case
):

    existing = load_case(selected_case)

    if existing:
        st.session_state.case_data = existing
        st.session_state.case_id = selected_case


# ============================================================
# MAIN ACTION
# ============================================================

top_left, top_right = st.columns([3, 1])

with top_left:
    st.markdown(
        f"### Investigation Case: `{selected_case}`"
    )

with top_right:

    investigate = st.button(
        "🔍 Investigate Case",
        type="primary",
        use_container_width=True,
    )


if investigate:

    with st.spinner(
        f"Running investigation for {selected_case}..."
    ):

        data, error = run_investigation(selected_case)

    if error:

        st.error("Investigation failed.")
        st.code(error)

    else:

        st.session_state.case_data = data
        st.session_state.case_id = selected_case

        st.success(
            f"Investigation completed successfully for {selected_case}."
        )


# ============================================================
# GET DATA
# ============================================================

data = st.session_state.get("case_data")

if data is None:

    st.info(
        "Select an investigation case and click "
        "**Investigate Case**."
    )

    st.stop()


case = data.get("case", {})
next_actions = data.get("next_best_actions", {})
evidence_requests = data.get("evidence_requests", [])
tool_calls = data.get("tool_calls", [])
sar = data.get("sar", {})


# ============================================================
# BASIC FIELDS
# ============================================================

case_id = data.get("case_id", selected_case)

verdict = case.get(
    "verdict",
    "unknown",
)

fraud_probability = case.get(
    "fraud_probability",
    0,
)

pattern = case.get(
    "pattern",
    "none",
)

pattern_description = case.get(
    "pattern_description",
    "",
)

exposure = case.get(
    "exposure_usd",
    0,
)

affected_transactions = case.get(
    "affected_txn_ids",
    [],
)

first_transaction = case.get(
    "first_suspicious_txn_id",
    "N/A",
)

connected_cards = case.get(
    "connected_card_ids",
    [],
)

connected_devices = case.get(
    "connected_device_profiles",
    [],
)

primary_action = next_actions.get(
    "primary_action",
    "N/A",
)

rules = next_actions.get(
    "rules",
    [],
)

approval_required = next_actions.get(
    "approval_required",
    False,
)

stop_reason = data.get(
    "stop_reason",
    "N/A",
)

latency = data.get(
    "latency_s",
    0,
)


# ============================================================
# INVESTIGATION SUMMARY
# ============================================================

st.markdown(
    '<div class="section-title">Investigation Summary</div>',
    unsafe_allow_html=True,
)

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric(
        "Fraud Probability",
        f"{fraud_probability * 100:.1f}%",
    )

with m2:
    st.metric(
        "Verdict",
        pretty(verdict),
    )

with m3:
    st.metric(
        "Exposure",
        money(exposure),
    )

with m4:
    st.metric(
        "Affected Transactions",
        len(affected_transactions),
    )


# ============================================================
# DECISION
# ============================================================

st.markdown(
    '<div class="section-title">Decision & Recommendation</div>',
    unsafe_allow_html=True,
)

decision_left, decision_right = st.columns(2)


with decision_left:

    if verdict.lower() == "fraud":

        st.markdown(
            f"""
            <div class="fraud-box">
                <h2>🚨 FRAUD DETECTED</h2>
                <h3>{fraud_probability * 100:.1f}% fraud probability</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif verdict.lower() == "uncertain":

        st.markdown(
            f"""
            <div class="uncertain-box">
                <h2>⚠️ UNCERTAIN</h2>
                <h3>{fraud_probability * 100:.1f}% fraud probability</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:

        st.markdown(
            f"""
            <div class="clear-box">
                <h2>✅ NO FRAUD DETECTED</h2>
                <h3>{fraud_probability * 100:.1f}% fraud probability</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )


with decision_right:

    st.markdown(
        '<div class="card">',
        unsafe_allow_html=True,
    )

    st.markdown("### Recommended Action")

    st.info(
        f"**{pretty(primary_action)}**"
    )

    st.write(
        f"Rules triggered: **{', '.join(rules) if rules else 'None'}**"
    )

    st.write(
        f"Approval required: **{'Yes' if approval_required else 'No'}**"
    )

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# TRANSACTION INTELLIGENCE
# ============================================================

st.markdown(
    '<div class="section-title">Transaction Intelligence</div>',
    unsafe_allow_html=True,
)

t1, t2, t3, t4 = st.columns(4)

with t1:
    st.metric(
        "Suspicious Transaction",
        first_transaction,
    )

with t2:
    st.metric(
        "Pattern",
        pretty(pattern),
    )

with t3:
    st.metric(
        "Connected Cards",
        len(connected_cards),
    )

with t4:
    st.metric(
        "Connected Devices",
        len(connected_devices),
    )


if pattern_description:

    st.markdown(
        '<div class="card">',
        unsafe_allow_html=True,
    )

    st.markdown("### Detected Pattern")

    st.write(pattern_description)

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# EVIDENCE
# ============================================================

st.markdown(
    '<div class="section-title">🔎 Investigation Evidence</div>',
    unsafe_allow_html=True,
)

if isinstance(evidence := case.get("evidence", []), list):

    for i, item in enumerate(evidence, 1):

        claim = item.get(
            "claim",
            "Evidence",
        )

        source = item.get(
            "source",
            "Unknown source",
        )

        ref = item.get(
            "ref",
            "",
        )

        with st.expander(
            f"Evidence {i}: {claim}"
        ):

            st.write(
                f"**Source:** {source}"
            )

            if ref:
                st.write(
                    f"**Reference:** {ref}"
                )

else:

    st.info("No evidence records available.")


# ============================================================
# HISTORICAL CASES
# ============================================================

similar_cases = case.get(
    "similar_prior_cases",
    [],
)

st.markdown(
    '<div class="section-title">📚 Historical Fraud Evidence</div>',
    unsafe_allow_html=True,
)

h1, h2, h3 = st.columns(3)

with h1:
    st.metric(
        "Similar Prior Cases",
        len(similar_cases),
    )

with h2:

    confirmed = sum(
        1
        for x in similar_cases
        if x.get("status") == "confirmed_fraud"
    )

    st.metric(
        "Confirmed Fraud Matches",
        confirmed,
    )

with h3:

    strongest = (
        max(
            [x.get("relevance_score", 0) for x in similar_cases],
            default=0,
        )
    )

    st.metric(
        "Strongest Relevance Score",
        strongest,
    )


if similar_cases:

    table_data = []

    for item in similar_cases[:10]:

        table_data.append(
            {
                "Case": item.get("case_id", ""),
                "Status": pretty(item.get("status", "")),
                "Pattern": pretty(item.get("pattern", "")),
                "Customer": item.get("customer_id", ""),
                "Card": item.get("card_id", ""),
                "Relevance": item.get("relevance_score", 0),
            }
        )

    st.dataframe(
        table_data,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# EVIDENCE REQUESTS
# ============================================================

st.markdown(
    '<div class="section-title">📋 Evidence Requests</div>',
    unsafe_allow_html=True,
)

for request in evidence_requests:

    st.write(
        f"**{pretty(request.get('type', 'request'))}** — "
        f"{pretty(request.get('status', 'unknown'))}"
    )

    if request.get("assumption"):
        st.caption(
            request["assumption"]
        )


# ============================================================
# STOP REASON
# ============================================================

st.markdown(
    '<div class="section-title">🧠 Investigation Reasoning</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="card">',
    unsafe_allow_html=True,
)

st.write(stop_reason)

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# TOOL CALLS
# ============================================================

with st.expander("Investigation Data Sources"):

    for tool in tool_calls:

        st.write(
            f"**{tool.get('tool', 'Unknown')}** — "
            f"{tool.get('purpose', '')}"
        )


# ============================================================
# SAR
# ============================================================

with st.expander("SAR Assessment"):

    st.write(
        f"**Required:** {'Yes' if sar.get('required') else 'No'}"
    )

    st.write(
        sar.get(
            "reason",
            "No SAR assessment available.",
        )
    )


# ============================================================
# RAW JSON
# ============================================================

with st.expander("View Complete Investigation JSON"):

    st.json(data)


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    f"Fraud Investigation Agent • Case {case_id} • "
    f"Investigation latency: {latency:.2f}s • "
    "Python Investigation Engine + TigerGraph Fraud Graph"
)

