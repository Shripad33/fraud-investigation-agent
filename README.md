# Fraud Investigation Agent — Hacker House Goa

An explainable fraud investigation agent built for the **Hacker House Goa** challenge. The system investigates suspicious transactions by combining transaction history, customer behavior, identity and device evidence, historical fraud cases, cross-customer activity, and relationship-based fraud modeling.

The project is designed to produce a structured investigation record containing evidence, findings, decisions, actions, and recommended next steps.

---

## 🚀 What This Project Does

The Fraud Investigation Agent takes a suspicious case and performs a structured investigation pipeline:

1. Loads the suspicious case.
2. Retrieves the flagged transaction.
3. Analyzes customer transaction history.
4. Calculates behavioral and transaction-level signals.
5. Checks identity and device evidence.
6. Searches historical closed fraud cases.
7. Analyzes related activity across customers.
8. Searches for similar transaction activity.
9. Calculates a temporary heuristic fraud probability.
10. Produces an explainable investigation result.
11. Records the recommended next-best action.
12. Saves the complete investigation result as a JSON case record.

---

# 🏗️ Architecture

```text
                    ┌──────────────────────┐
                    │   Suspicious Case    │
                    │      HHG-XXX         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Investigation Agent  │
                    │    Python Engine      │
                    └──────────┬───────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
 ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
 │ Transaction     │  │ Customer        │  │ Identity /      │
 │ History         │  │ Behaviour       │  │ Device Evidence │
 └─────────────────┘  └─────────────────┘  └─────────────────┘
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Historical Cases &   │
                    │ Cross-Customer       │
                    │ Relationship Analysis│
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Evidence Aggregation │
                    │ & Decision Engine    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Investigation Result │
                    │ • Verdict            │
                    │ • Risk assessment    │
                    │ • Evidence           │
                    │ • Next action        │
                    │ • Case record        │
                    └──────────────────────┘

             ┌──────────────────────────────┐
             │       TigerGraph Layer      │
             │                              │
             │ Customer                     │
             │ Account                      │
             │ Card                         │
             │ Transaction                  │
             │ DeviceProfile                │
             │ EmailDomain                  │
             │ BillingRegion                │
             │ ClosedCase                   │
             └──────────────────────────────┘
```

---

# 🕸️ TigerGraph Fraud Graph

The project models the fraud ecosystem as a connected graph using **TigerGraph**.

### Vertex Types

* `Customer`
* `Account`
* `Card`
* `Transaction`
* `DeviceProfile`
* `EmailDomain`
* `BillingRegion`
* `ClosedCase`

### Edge Types

* `OWNS`
* `MADE`
* `ON_CARD`
* `FROM_DEVICE`
* `PURCHASER_EMAIL`
* `BILLED_IN`
* `NEXT`
* `INVOLVES`
* `CONNECTED_TO`

This structure allows fraud-related entities to be represented as relationships instead of isolated records.

The TigerGraph graph was populated with the project's fraud data and successfully queried during development.

---

# 🔎 Investigation Engine

The Python investigation engine performs a multi-stage investigation.

### Investigation stages

```text
[1] Load case
      ↓
[2] Load transaction index
      ↓
[3] Retrieve flagged transaction
      ↓
[4] Load customer transaction history
      ↓
[5] Analyze customer behaviour
      ↓
[6] Load identity/device evidence
      ↓
[7] Search historical closed cases
      ↓
[8] Check cross-customer activity
      ↓
[9] Search similar transaction activity
      ↓
[10] Calculate heuristic probability
      ↓
[11] Generate investigation decision
      ↓
[12] Save case JSON
```

---

# 📊 20-Case Evaluation

The investigation agent was evaluated against all **20 cases** provided in the Hacker House Goa case pack.

| Case    | Customer | Flagged Transaction |
| ------- | -------- | ------------------: |
| HHG-001 | C12382   |             3514030 |
| HHG-002 | C11891   |             3478782 |
| HHG-003 | C08623   |             3530164 |
| HHG-004 | C08106   |             3583227 |
| HHG-005 | C02923   |             3523199 |
| HHG-006 | C07297   |             3476682 |
| HHG-007 | C09933   |             3514948 |
| HHG-008 | C13171   |             3558054 |
| HHG-009 | C08299   |             3581141 |
| HHG-010 | C10434   |             3506725 |
| HHG-011 | C11923   |             3583368 |
| HHG-012 | C05876   |             3553342 |
| HHG-013 | C07671   |             3526826 |
| HHG-014 | C13487   |             3478561 |
| HHG-015 | C03042   |             3464869 |
| HHG-016 | C09988   |             3534820 |
| HHG-017 | C04570   |             3450629 |
| HHG-018 | C02354   |             3491361 |
| HHG-019 | C07987   |             3503878 |
| HHG-020 | C12265   |             3509359 |

### Validation Result

```text
Total cases : 20
Passed      : 20
Failed      : 0
```

The complete 20-case pack passed the project's automated output validation.

---

# 🧪 Example Investigation

## HHG-002

The agent combines multiple independent signals including:

* Transaction behaviour
* Customer history
* Identity evidence
* Device evidence
* Historical fraud cases
* Cross-customer activity
* Similar transaction activity

Example result:

```text
Case              : HHG-002
Fraud probability : 0.94
```

The 94% value is a **temporary heuristic fraud probability**, not a calibrated machine-learning probability.

The investigation output also contains:

* Verdict
* Pattern
* Evidence
* Findings
* Exposure
* Recommended action
* Next-best action
* Historical evidence
* Investigation metadata

---

# 🧠 Agentic Capabilities

The project implements several investigation-oriented agent capabilities:

### Evidence Gathering

The system automatically gathers evidence from multiple structured sources before reaching a decision.

### Multi-Signal Reasoning

Instead of relying on a single transaction attribute, the engine combines behavioural, transactional, identity, device, historical, and relationship signals.

### Historical Case Reasoning

Previous closed cases are searched to identify relevant historical patterns.

### Cross-Customer Analysis

The engine checks related activity involving other customers within relevant regions and time windows.

### Explainable Decisions

The final investigation includes the evidence and factors contributing to the decision rather than returning only a risk number.

### Next-Best Action

The system produces an actionable recommendation such as additional verification or step-up authentication when the evidence does not support immediate closure.

### Uncertain Outcomes

The agent can return an `uncertain` result when additional evidence could materially change the investigation.

---

# 📁 Project Structure

```text
fraud-agent/
│
├── app.py
├── README.md
├── requirements.txt
├── .gitignore
│
├── cases/
│   ├── HHG-001.json
│   ├── HHG-002.json
│   ├── ...
│   └── HHG-020.json
│
├── data/
│   ├── case_pack.csv
│   ├── transactions.csv
│   ├── transactions_demo.csv
│   └── tigergraph/
│       └── tigergraph_client.py
│
├── outputs/
│   └── transaction_index.json
│
├── scripts/
│   ├── build_index.py
│   ├── decision_engine.py
│   ├── investigate_case.py
│   └── validate_cases.py
│
├── extract_customer_history.py
└── extract_demo.py
```

---

# ⚙️ Local Setup

## 1. Clone the repository

```bash
git clone https://github.com/Shripad33/fraud-investigation-agent.git
cd fraud-investigation-agent
```

## 2. Create a virtual environment

Windows:

```powershell
python -m venv .venv
```

## 3. Activate the environment

```powershell
.\.venv\Scripts\activate
```

If PowerShell execution policy prevents activation, the environment can be used directly without activation:

```powershell
.\.venv\Scripts\python.exe
```

## 4. Install dependencies

```powershell
pip install -r requirements.txt
```

---

# ▶️ Run an Investigation

Example:

```powershell
.\.venv\Scripts\python.exe .\scripts\investigate_case.py --case HHG-002
```

Another example:

```powershell
.\.venv\Scripts\python.exe .\scripts\investigate_case.py --case HHG-020
```

The investigation result is saved under:

```text
cases/
```

---

# 🧪 Validate All Cases

Run:

```powershell
.\.venv\Scripts\python.exe .\scripts\validate_cases.py
```

Expected result:

```text
Total cases : 20
Passed      : 20
Failed      : 0
```

---

# 🌐 Streamlit Interface

The project includes a Streamlit interface for demonstrating investigations interactively.

Run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Then open:

```text
http://localhost:8501
```

The interface provides:

* Case selection
* Investigation execution
* Fraud probability
* Verdict
* Exposure
* Evidence
* Detected pattern
* Recommended action
* Historical cases
* Evidence requests
* Investigation metadata
* Raw JSON output

---

# 📦 Dataset

The working transaction dataset used by the investigation engine contains:

```text
Transactions : 26,643
Customers    : 20
Regions      : 96
Cases        : 20
```

The repository also contains a smaller demonstration transaction dataset:

```text
data/transactions_demo.csv
```

Large source/backup files are intentionally excluded from Git history to keep the repository lightweight.

---

# 🔐 Security

Secrets and credentials are not stored in the repository.

Environment variables can be used for external TigerGraph configuration:

```text
TG_HOST
TG_TOKEN
```

Example:

```powershell
$env:TG_HOST="https://your-tigergraph-host"
$env:TG_TOKEN="your-token"
```

Never commit API tokens, passwords, or other credentials to GitHub.

---

# 🛠️ Technology Stack

* **Python**
* **Streamlit**
* **Pandas**
* **TigerGraph**
* **pyTigerGraph**
* **JSON**
* **CSV**
* **PowerShell**
* **Git / GitHub**

---

# 📌 Current Implementation

The current prototype provides:

* End-to-end suspicious transaction investigation
* 20-case evaluation
* Automated case validation
* Structured JSON investigation records
* Explainable evidence aggregation
* Next-best-action recommendations
* Streamlit demonstration interface
* TigerGraph fraud data model
* TigerGraph schema and query demonstration
* Reproducible local setup

The Python investigation engine and TigerGraph graph are currently separate components. The graph is populated and queryable, while automated case-writeback from the Python investigation engine into TigerGraph is identified as a future integration step.

---

# 🚀 Future Improvements

With additional development time, the system could be extended with:

1. Direct automated case write-back into TigerGraph.
2. Live graph traversal during every investigation.
3. Graph-based fraud ring detection.
4. Calibrated machine-learning fraud probabilities.
5. Real-time transaction ingestion.
6. Automated SAR generation and submission workflows.
7. Human approval workflows for high-risk actions.
8. More advanced device and identity linkage.
9. Production authentication and access control.
10. Monitoring and investigation analytics dashboards.

---

# 💡 What We Learned

This project demonstrated how fraud investigations can be structured as an evidence-gathering and decision-support workflow rather than a simple binary classification problem.

Key learnings include:

* Combining multiple independent evidence sources improves investigation explainability.
* Historical cases provide useful contextual evidence.
* Graph modeling is valuable for representing relationships between customers, transactions, devices, cards, and other entities.
* Investigation systems need to support uncertainty rather than forcing every case into a binary outcome.
* Explainability and recommended next actions are important for human investigators.
* Separating the investigation engine from the graph data layer makes it easier to evolve the architecture.

---

# ⚠️ Disclaimer

This project is a prototype developed for the Hacker House Goa challenge.

Fraud probabilities generated by the current investigation engine are heuristic investigation signals and should not be interpreted as calibrated production fraud probabilities.

The system is intended for demonstration, experimentation, and research purposes.
