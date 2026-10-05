"""
Governed Agentic AI - Fraud Investigation Console (PoC UI)
Run from C:\\fraud-agentic-poc :  streamlit run ui\\app.py
Synthetic data only.
"""
import time
import os
import re

import pandas as pd
import requests
import streamlit as st

DATA_API = "http://127.0.0.1:8000"
N8N_WEBHOOK = "http://localhost:5678/webhook/fraud-alert"
N8N_API_BASE = os.getenv("N8N_API_BASE", "http://localhost:5678/api/v1")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
MODELS = ["qwen2.5:3b", "llama3.2:3b", "gemma2:2b", "qwen2.5:7b", "llama3.1:8b", "mistral:7b"]


def clear_case():
    st.session_state.case = None
    st.session_state.resume_url = None
    st.session_state.decided = None
    st.session_state.elapsed = None
    st.session_state.running = False


def cancel_n8n_execution():
    """Stop the current n8n execution if an n8n API key is configured."""
    execution_id = st.session_state.get("n8n_execution_id")
    if not execution_id:
        return False, "No n8n execution ID is available for this case."

    if not N8N_API_KEY:
        return False, (
            "UI result cleared, but the n8n execution was not stopped. "
            "Set the N8N_API_KEY environment variable to enable real execution cancellation."
        )

    try:
        r = requests.post(
            f"{N8N_API_BASE}/executions/{execution_id}/stop",
            headers={"X-N8N-API-KEY": N8N_API_KEY},
            timeout=10,
        )
        if r.ok:
            return True, f"n8n execution {execution_id} stopped."
        return False, f"n8n stop request failed ({r.status_code}): {r.text}"
    except Exception as e:
        return False, f"Could not stop n8n execution: {e}"

st.set_page_config(page_title="Fraud Investigation Console", layout="wide")
st.title("Governed Agentic AI - Fraud Investigation Console")
st.caption("Proof of concept. Synthetic data only. The AI recommends; the investigator decides.")

if "case" not in st.session_state:
    st.session_state.case = None

if "resume_url" not in st.session_state:
    st.session_state.resume_url = None

if "decided" not in st.session_state:
    st.session_state.decided = None

if "elapsed" not in st.session_state:
    st.session_state.elapsed = None

if "running" not in st.session_state:
    st.session_state.running = False

if "n8n_execution_id" not in st.session_state:
    st.session_state.n8n_execution_id = None

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Session")
    role = st.selectbox("Your role", ["investigator", "supervisor"])
    model = st.selectbox("Model", MODELS)
    st.markdown("---")
    st.caption("Services")
    for name, url in [("Data API", DATA_API + "/health")]:
        try:
            ok = requests.get(url, timeout=3).ok
        except Exception:
            ok = False
        st.write(("Online: " if ok else "OFFLINE: ") + name)

tab_case, tab_audit = st.tabs(["Investigate alert", "Audit log"])

# ---------------- Investigate tab ----------------
with tab_case:
    try:
        alerts = requests.get(DATA_API + "/alerts", timeout=5).json()
    except Exception:
        alerts = []
        st.error("Data API not reachable. Start it: uvicorn main:app --port 8000 (from the data_api folder).")

    if alerts:
        df = pd.DataFrame(alerts)
        c1, c2 = st.columns([1, 2])
        with c1:
            alert_id = st.selectbox("Select fraud alert", df["alert_id"].tolist())
        with c2:
            st.dataframe(df[df.alert_id == alert_id], hide_index=True, use_container_width=True)

        run_col, clear_col, cancel_col = st.columns([2, 1, 1])

        with run_col:
            run_clicked = st.button("Run agentic investigation", type="primary")

        with clear_col:
            clear_clicked = st.button("Clear result")

        with cancel_col:
            cancel_clicked = st.button("Cancel execution", disabled=not bool(st.session_state.get("n8n_execution_id")))

        if clear_clicked:
            clear_case()
            st.rerun()

        if cancel_clicked:
            ok, message = cancel_n8n_execution()
            clear_case()
            st.session_state.n8n_execution_id = None
            if ok:
                st.success(message)
            else:
                st.warning(message)
            st.rerun()

        if run_clicked:
            clear_case()
            st.session_state.n8n_execution_id = None
            st.session_state.running = True

            start = time.time()

            with st.spinner("Orchestrator running agents... this can take a few minutes on CPU"):
                try:
                    r = requests.post(
                        N8N_WEBHOOK,
                        json={
                            "alert_id": alert_id,
                            "model": model
                        },
                        timeout=900
                    )

                    r.raise_for_status()

                    # If the webhook response exposes an execution id, retain it
                    # so the Cancel execution button can stop that run through
                    # the n8n API. The normal case response does not always include it.
                    execution_id = (
                        r.headers.get("x-n8n-execution-id")
                        or r.headers.get("x-execution-id")
                    )
                    try:
                        response_data = r.json()
                        if isinstance(response_data, dict):
                            execution_id = execution_id or response_data.get("execution_id")
                    except Exception:
                        response_data = None

                    st.session_state.n8n_execution_id = execution_id

                    # Parse the response returned by n8n
                    data = response_data if response_data is not None else r.json()

                    # n8n may return either:
                    # 1) {"case": {...}, "resume_url": "..."}
                    # OR
                    # 2) the case object directly, with "resume_url" at the top level.
                    #
                    # Your current workflow returns format (2), so support both.
                    if isinstance(data, dict) and isinstance(data.get("case"), dict):
                        case = data["case"]
                    else:
                        case = data.copy() if isinstance(data, dict) else None

                    resume_url = (
                        data.get("resume_url")
                        if isinstance(data, dict)
                        else None
                    )

                    # n8n's resume URL contains the waiting execution ID:
                    # /webhook-waiting/<execution_id>?signature=...
                    # Use it as a fallback when n8n does not expose the ID
                    # in a response header/body.
                    if not st.session_state.n8n_execution_id and resume_url:
                        match = re.search(r"/webhook-waiting/(\\d+)", str(resume_url))
                        if match:
                            st.session_state.n8n_execution_id = match.group(1)

                    # resume_url is not part of the case itself
                    if isinstance(case, dict):
                        case.pop("resume_url", None)

                    st.session_state.case = case
                    st.session_state.resume_url = resume_url
                    st.session_state.elapsed = round(time.time() - start, 1)
                    st.session_state.running = False

                    if not case:
                        st.error("n8n returned a response, but no case was found.")
                        st.json(data)

                    elif not resume_url:
                        st.warning(
                            "Investigation result received, but no resume URL was returned."
                        )

                except requests.exceptions.ConnectionError:
                    st.session_state.running = False
                    st.error(
                        "Cannot reach n8n. Is it running, and is the workflow active?"
                    )

                except requests.exceptions.Timeout:
                    st.session_state.running = False
                    st.error(
                        "Workflow timed out while waiting for n8n. "
                        "Check the n8n execution and Respond to Webhook node."
                    )

                except ValueError:
                    st.session_state.running = False
                    st.error("n8n returned a non-JSON response.")
                    st.code(r.text)

                except Exception as e:
                    st.session_state.running = False
                    st.error(f"Workflow error: {e}")

    case = st.session_state.case
    if case:
        st.markdown("---")
        st.subheader(f"Case {case['alert_id']}  |  model: {case['model']}")

        top_clear, top_cancel = st.columns([1, 1])
        with top_clear:
            if st.button("Clear result", key="clear_result_top"):
                clear_case()
                st.session_state.n8n_execution_id = None
                st.rerun()
        with top_cancel:
            if st.button(
                "Cancel execution",
                key="cancel_execution_top",
                disabled=not bool(st.session_state.get("n8n_execution_id")),
            ):
                ok, message = cancel_n8n_execution()
                clear_case()
                st.session_state.n8n_execution_id = None
                if ok:
                    st.success(message)
                else:
                    st.warning(message)
                st.rerun()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Route", case.get("route", "-"))
        m2.metric("Risk score", case.get("risk_score") if case.get("risk_score") is not None else "n/a")
        m3.metric("System action", str(case.get("final_action", "-")).upper())
        m4.metric("Queue", case.get("queue", "-"))

        if case.get("route") == "EXCEPTION_ESCALATE":
            st.error("EXCEPTION: " + "; ".join(case.get("reasons", [])))
        elif case.get("route") == "INJECTION_HOLD":
            st.error("Guardrail triggered: possible prompt injection in the free-text note. Held for review.")
        elif case.get("escalate"):
            st.warning("ESCALATION: senior review required. " + "; ".join(case.get("reasons", [])))
        else:
            st.success("Standard review. " + "; ".join(case.get("reasons", [])))

        if case.get("hallucination_flag"):
            st.warning("Quality flag: an agent cited a rule that was not in the evidence.")

        rec = case.get("recommendation")
        if rec:
            st.markdown("### Recommendation")
            st.info(rec.get("headline", ""))
            a, b = st.columns(2)
            with a:
                st.markdown("**Key evidence**")
                for x in rec.get("key_evidence", []):
                    st.write("- " + str(x))
            with b:
                st.markdown("**Suggested next steps**")
                for x in rec.get("next_steps", []):
                    st.write("- " + str(x))
            st.caption("Risk if wrong: " + str(rec.get("risk_if_wrong", "")))

        findings = case.get("agent_findings")
        if findings:
            with st.expander("Agent outputs (transparency)"):
                for k, v in findings.items():
                    st.markdown(f"**{k.title()} agent**")
                    st.json(v)
        st.caption(f"Schema valid: {case.get('schema_valid')}  |  agent time: {case.get('total_latency_s')} s  |  wall time: {st.session_state.get('elapsed', '-')} s")

        # ---------------- Human-in-the-loop ----------------
        st.markdown("---")
        st.subheader("Human decision (required)")
        if st.session_state.decided:
            d = st.session_state.decided
            st.success(f"Decision recorded: {d.get('human_decision')} | outcome: {d.get('final_outcome', '')}")
            st.write("Audit comment: " + str(d.get("human_comment", "")))
        elif not st.session_state.resume_url:
            st.info("No pending decision for this case.")
        else:
            decision = st.radio("Decision", ["approve", "reject", "escalate"], horizontal=True,
                                help="approve = accept the recommendation; reject = override it; escalate = send to supervisor")
            comment = st.text_area("Comment (mandatory for approve / reject)")
            if decision == "reject" and case.get("final_action") == "hold" and role != "supervisor":
                st.warning("Overriding a HOLD requires the supervisor role. Submitting will escalate instead.")
            if st.button("Submit decision"):
                if decision != "escalate" and len(comment.strip()) < 5:
                    st.error("A comment of at least 5 characters is required.")
                else:
                    try:
                        requests.post(st.session_state.resume_url,
                                      json={"decision": decision, "comment": comment, "role": role}, timeout=60)
                        time.sleep(2)
                        rows = requests.get(DATA_API + "/audit", params={"_t": time.time()}, timeout=5).json()
                        mine = [r for r in rows if r["alert_id"] == case["alert_id"]]
                        last = mine[-1] if mine else {"human_decision": decision, "human_comment": comment}
                        last["final_outcome"] = "see audit log"
                        st.session_state.decided = last
                        st.session_state.n8n_execution_id = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not submit decision: {e}")

# ---------------- Audit tab ----------------
with tab_audit:
    st.subheader("Audit log")
    if st.button("Refresh"):
        st.rerun()
    try:
        rows = requests.get(DATA_API + "/audit", params={"_t": time.time()}, timeout=5).json()
        if rows:
            audit_df = pd.DataFrame(rows)
            if "logged_at" in audit_df.columns:
                audit_df = audit_df.sort_values("logged_at", ascending=False)
            st.dataframe(audit_df, hide_index=True, use_container_width=True)
        else:
            st.info("No decisions logged yet.")
    except Exception:
        st.error("Audit log not reachable.")
