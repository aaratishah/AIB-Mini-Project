"""
Data / tools service for the governed agentic fraud-investigation PoC.
Run from the data_api folder:  uvicorn main:app --port 8000
Serves synthetic evidence to n8n and stores the audit log.
Ground-truth labels are NEVER returned to the agents.
"""
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)
AUDIT_FILE = RESULTS / "audit_log.csv"

AUDIT_COLUMNS = [
    "logged_at", "alert_id", "model", "agent_action", "risk_level",
    "risk_score", "confidence", "schema_valid", "route", "human_decision",
    "human_comment", "escalated", "latency_s",
]


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / name, dtype=str).fillna("")


alerts = load("alerts.csv")
customers = load("customers.csv")
transactions = load("transactions.csv")
devices = load("devices.csv")
rules = json.loads((DATA / "rules.json").read_text())

# Labels used only for offline scoring, never sent to agents
HIDDEN_COLUMNS = ["ground_truth_action", "ground_truth_escalate", "case_type"]

app = FastAPI(title="Fraud PoC Data API")


@app.get("/health")
def health():
    return {"status": "ok", "alerts": len(alerts)}


@app.get("/alerts")
def list_alerts():
    """Alert IDs for the UI dropdown (no labels)."""
    cols = ["alert_id", "customer_id", "amount", "country", "channel"]
    return alerts[cols].to_dict(orient="records")


@app.get("/rules")
def get_rules():
    return rules


@app.get("/evidence/{alert_id}")
def evidence(alert_id: str):
    row = alerts[alerts.alert_id == alert_id]
    if row.empty:
        return {"found": False, "alert_id": alert_id, "missing_fields": ["alert"]}

    alert = row.iloc[0].drop(labels=HIDDEN_COLUMNS).to_dict()

    # Required-field check (device is not required for ATM channel)
    required = ["customer_id", "amount", "timestamp", "country", "channel"]
    if alert["channel"] != "ATM":
        required.append("device_id")
    missing = [f for f in required if alert.get(f, "") == ""]

    # Customer profile
    cust_row = customers[customers.customer_id == alert["customer_id"]]
    customer = cust_row.iloc[0].to_dict() if not cust_row.empty else None
    if customer is None and "customer_id" not in missing:
        missing.append("customer_profile")

    # Device record
    dev_row = devices[devices.device_id == alert["device_id"]]
    device = dev_row.iloc[0].to_dict() if not dev_row.empty else None

    # Recent history (excluding the alerted transaction) and velocity
    hist = transactions[
        (transactions.customer_id == alert["customer_id"])
        & (transactions.txn_id != alert["txn_id"])
    ].copy()
    recent, velocity_10min = [], 0
    if not hist.empty and alert["timestamp"]:
        hist["ts"] = pd.to_datetime(hist["timestamp"])
        t0 = pd.to_datetime(alert["timestamp"])
        hist = hist[hist.ts <= t0].sort_values("ts", ascending=False)
        velocity_10min = int((hist.ts >= t0 - timedelta(minutes=10)).sum())
        recent = hist.head(5).drop(columns=["ts"]).to_dict(orient="records")

    amount_ratio = None
    if customer and alert["amount"]:
        amount_ratio = round(float(alert["amount"]) / float(customer["avg_txn_amount"]), 1)

    return {
        "found": True,
        "alert": alert,
        "customer": customer,
        "device": device,
        "recent_transactions": recent,
        "prior_txns_in_last_10_min": velocity_10min,
        "amount_vs_average_ratio": amount_ratio,
        "missing_fields": missing,
        "is_complete": len(missing) == 0,
        "rule_weights": rules["rules"],
        "thresholds": rules["thresholds"],
        "policy": rules["policy"],
    }


class AuditEntry(BaseModel):
    alert_id: str
    model: str = ""
    agent_action: str = ""
    risk_level: str = ""
    risk_score: float | None = None
    confidence: float | None = None
    schema_valid: bool | None = None
    route: str = ""
    human_decision: str = ""
    human_comment: str = ""
    escalated: bool | None = None
    latency_s: float | None = None


@app.post("/audit")
def write_audit(entry: AuditEntry):
    new_file = not AUDIT_FILE.exists()
    record = entry.model_dump()
    record["logged_at"] = datetime.now().isoformat(timespec="seconds")
    with open(AUDIT_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=AUDIT_COLUMNS)
        if new_file:
            w.writeheader()
        w.writerow({k: record.get(k, "") for k in AUDIT_COLUMNS})
    return {"status": "logged", "alert_id": entry.alert_id}


@app.get("/audit")
def read_audit():
    if not AUDIT_FILE.exists():
        return []
    return pd.read_csv(AUDIT_FILE).fillna("").to_dict(orient="records")
