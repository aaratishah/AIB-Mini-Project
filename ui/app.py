"""
Governed Agentic AI - Fraud Investigation Console (PoC UI)

Synthetic data only.
The AI recommends; the investigator decides.
"""

import time
import os
import re

import pandas as pd
import requests
import streamlit as st


# ============================================================
# CONFIGURATION
# ============================================================

# Public ngrok URL
# This single URL points to the local proxy on port 9000.
# The proxy routes:
#   Data API -> localhost:8000
#   n8n      -> localhost:5678

DATA_API = "https://awhile-twisting-nursing.ngrok-free.dev"

N8N_BASE = "https://awhile-twisting-nursing.ngrok-free.dev"

N8N_WEBHOOK = N8N_BASE + "/webhook/fraud-alert"


# Optional n8n API configuration.
# This is only needed for the optional Cancel Execution feature.
N8N_API_BASE = os.getenv(
    "N8N_API_BASE",
    "http://localhost:5678/api/v1"
)

N8N_API_KEY = os.getenv(
    "N8N_API_KEY",
    ""
)


MODELS = [
    "qwen2.5:3b",
    "llama3.2:3b",
    "gemma2:2b",
    "qwen2.5:7b",
    "llama3.1:8b",
    "mistral:7b"
]


# ============================================================
# STREAMLIT PAGE
# ============================================================

st.set_page_config(
    page_title="Fraud Investigation Console",
    layout="wide"
)

st.title(
    "Governed Agentic AI - Fraud Investigation Console"
)

st.caption(
    "Proof of concept. Synthetic data only. "
    "The AI recommends; the investigator decides."
)


# ============================================================
# SESSION STATE
# ============================================================

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


# ============================================================
# HELPER: CLEAR CASE
# ============================================================

def clear_case():
    """
    Clear the current case from the Streamlit UI.
    """

    st.session_state.case = None
    st.session_state.resume_url = None
    st.session_state.decided = None
    st.session_state.elapsed = None
    st.session_state.running = False
    st.session_state.n8n_execution_id = None


# ============================================================
# HELPER: CONVERT RESUME URL
# ============================================================

def convert_resume_url_to_public(resume_url):
    """
    n8n normally returns something like:

    http://localhost:5678/webhook-waiting/278?signature=...

    Streamlit Cloud cannot access the laptop's localhost.

    Convert it to:

    https://awhile-twisting-nursing.ngrok-free.dev/webhook-waiting/278?signature=...
    """

    if not resume_url:
        return None

    resume_url = str(resume_url)

    replacements = [
        "http://localhost:5678",
        "http://127.0.0.1:5678",
        "https://localhost:5678",
        "https://127.0.0.1:5678"
    ]

    for local_base in replacements:

        if resume_url.startswith(local_base):

            resume_url = (
                N8N_BASE
                +
                resume_url[len(local_base):]
            )

            break

    return resume_url


# ============================================================
# HELPER: CANCEL N8N EXECUTION
# ============================================================

def cancel_n8n_execution():
    """
    Stop the current n8n execution if an n8n API key
    is configured.

    This feature is optional.
    """

    execution_id = (
        st.session_state.get(
            "n8n_execution_id"
        )
    )

    if not execution_id:

        return (
            False,
            "No n8n execution ID is available for this case."
        )


    if not N8N_API_KEY:

        return (
            False,
            "UI result cleared, but the n8n execution "
            "was not stopped. Set the N8N_API_KEY "
            "environment variable to enable real "
            "execution cancellation."
        )


    try:

        r = requests.post(
            f"{N8N_API_BASE}/executions/{execution_id}/stop",
            headers={
                "X-N8N-API-KEY": N8N_API_KEY
            },
            timeout=10
        )


        if r.ok:

            return (
                True,
                f"n8n execution {execution_id} stopped."
            )


        return (
            False,
            f"n8n stop request failed "
            f"({r.status_code}): {r.text}"
        )


    except Exception as e:

        return (
            False,
            f"Could not stop n8n execution: {e}"
        )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("Session")


    role = st.selectbox(
        "Your role",
        [
            "investigator",
            "supervisor"
        ]
    )


    model = st.selectbox(
        "Model",
        MODELS
    )


    st.markdown("---")

    st.caption("Services")


    # --------------------------------------------------------
    # Data API health
    # --------------------------------------------------------

    try:

        health_response = requests.get(
            DATA_API + "/health",
            timeout=10
        )


        if health_response.ok:

            st.write(
                "Online: Data API"
            )

        else:

            st.write(
                "OFFLINE: Data API"
            )


    except Exception:

        st.write(
            "OFFLINE: Data API"
        )


# ============================================================
# TABS
# ============================================================

tab_case, tab_audit = st.tabs(
    [
        "Investigate alert",
        "Audit log"
    ]
)


# ============================================================
# INVESTIGATION TAB
# ============================================================

with tab_case:


    # ========================================================
    # LOAD ALERTS
    # ========================================================

    try:

        alerts_response = requests.get(
            DATA_API + "/alerts",
            timeout=10
        )

        alerts_response.raise_for_status()

        alerts = alerts_response.json()


    except Exception:

        alerts = []

        st.error(
            "Data API not reachable. "
            "Make sure the Data API, proxy and ngrok "
            "are running."
        )


    # ========================================================
    # DISPLAY ALERTS
    # ========================================================

    if alerts:

        df = pd.DataFrame(
            alerts
        )


        c1, c2 = st.columns(
            [1, 2]
        )


        with c1:

            alert_id = st.selectbox(
                "Select fraud alert",
                df["alert_id"].tolist()
            )


        with c2:

            st.dataframe(
                df[
                    df.alert_id == alert_id
                ],
                hide_index=True,
                use_container_width=True
            )


        # ====================================================
        # ACTION BUTTONS
        # ====================================================

        run_col, clear_col, cancel_col = st.columns(
            [2, 1, 1]
        )


        with run_col:

            run_clicked = st.button(
                "Run agentic investigation",
                type="primary"
            )


        with clear_col:

            clear_clicked = st.button(
                "Clear result"
            )


        with cancel_col:

            cancel_clicked = st.button(
                "Cancel execution",
                disabled=not bool(
                    st.session_state.get(
                        "n8n_execution_id"
                    )
                )
            )


        # ====================================================
        # CLEAR RESULT
        # ====================================================

        if clear_clicked:

            clear_case()

            st.rerun()


        # ====================================================
        # CANCEL EXECUTION
        # ====================================================

        if cancel_clicked:

            ok, message = cancel_n8n_execution()

            clear_case()


            if ok:

                st.success(
                    message
                )

            else:

                st.warning(
                    message
                )


            st.rerun()


        # ====================================================
        # RUN INVESTIGATION
        # ====================================================

        if run_clicked:

            clear_case()

            st.session_state.running = True

            start = time.time()


            with st.spinner(
                "Orchestrator running agents... "
                "this can take a few minutes on CPU"
            ):

                try:

                    # --------------------------------------------
                    # CALL PUBLIC N8N WEBHOOK
                    # --------------------------------------------

                    r = requests.post(
                        N8N_WEBHOOK,
                        json={
                            "alert_id": alert_id,
                            "model": model
                        },
                        timeout=900
                    )


                    r.raise_for_status()


                    # --------------------------------------------
                    # TRY TO GET EXECUTION ID
                    # --------------------------------------------

                    execution_id = (
                        r.headers.get(
                            "x-n8n-execution-id"
                        )
                        or
                        r.headers.get(
                            "x-execution-id"
                        )
                    )


                    # --------------------------------------------
                    # PARSE N8N RESPONSE
                    # --------------------------------------------

                    try:

                        response_data = r.json()


                        if isinstance(
                            response_data,
                            dict
                        ):

                            execution_id = (
                                execution_id
                                or
                                response_data.get(
                                    "execution_id"
                                )
                            )


                    except Exception:

                        response_data = None


                    st.session_state.n8n_execution_id = (
                        execution_id
                    )


                    # --------------------------------------------
                    # USE PARSED RESPONSE
                    # --------------------------------------------

                    data = (
                        response_data
                        if response_data is not None
                        else r.json()
                    )


                    # =================================================
                    # SUPPORT BOTH N8N RESPONSE FORMATS
                    # =================================================
                    #
                    # Format 1:
                    #
                    # {
                    #   "case": {...},
                    #   "resume_url": "..."
                    # }
                    #
                    # Format 2:
                    #
                    # {
                    #   "alert_id": "A01",
                    #   "route": "...",
                    #   ...
                    #   "resume_url": "..."
                    # }
                    #
                    # Your current workflow uses Format 2.
                    # =================================================

                    if (
                        isinstance(
                            data,
                            dict
                        )
                        and
                        isinstance(
                            data.get("case"),
                            dict
                        )
                    ):

                        case = data["case"]

                    else:

                        case = (
                            data.copy()
                            if isinstance(
                                data,
                                dict
                            )
                            else None
                        )


                    # --------------------------------------------
                    # GET RESUME URL
                    # --------------------------------------------

                    resume_url = (
                        data.get(
                            "resume_url"
                        )
                        if isinstance(
                            data,
                            dict
                        )
                        else None
                    )


                    # --------------------------------------------
                    # CONVERT LOCALHOST URL
                    # TO PUBLIC NGROK URL
                    # --------------------------------------------

                    resume_url = (
                        convert_resume_url_to_public(
                            resume_url
                        )
                    )


                    # --------------------------------------------
                    # EXTRACT EXECUTION ID
                    # FROM RESUME URL
                    # --------------------------------------------

                    if (
                        not st.session_state.n8n_execution_id
                        and
                        resume_url
                    ):

                        match = re.search(
                            r"/webhook-waiting/(\d+)",
                            str(resume_url)
                        )


                        if match:

                            st.session_state.n8n_execution_id = (
                                match.group(1)
                            )


                    # --------------------------------------------
                    # REMOVE RESUME URL FROM DISPLAYED CASE
                    # --------------------------------------------

                    if isinstance(
                        case,
                        dict
                    ):

                        case.pop(
                            "resume_url",
                            None
                        )


                    # --------------------------------------------
                    # SAVE RESULT
                    # --------------------------------------------

                    st.session_state.case = case

                    st.session_state.resume_url = (
                        resume_url
                    )

                    st.session_state.elapsed = round(
                        time.time() - start,
                        1
                    )

                    st.session_state.running = False


                    # --------------------------------------------
                    # VALIDATION
                    # --------------------------------------------

                    if not case:

                        st.error(
                            "n8n returned a response, "
                            "but no case was found."
                        )

                        st.json(
                            data
                        )


                    elif not resume_url:

                        st.warning(
                            "Investigation result received, "
                            "but no resume URL was returned. "
                            "Human-in-the-loop may not be available."
                        )


                # ====================================================
                # ERROR HANDLING
                # ====================================================

                except requests.exceptions.ConnectionError:

                    st.session_state.running = False

                    st.error(
                        "Cannot reach n8n. "
                        "Make sure n8n, the proxy and ngrok "
                        "are running."
                    )


                except requests.exceptions.Timeout:

                    st.session_state.running = False

                    st.error(
                        "Workflow timed out while waiting for n8n. "
                        "Check the n8n execution and Respond to "
                        "Webhook node."
                    )


                except ValueError:

                    st.session_state.running = False

                    st.error(
                        "n8n returned a non-JSON response."
                    )

                    st.code(
                        r.text
                    )


                except Exception as e:

                    st.session_state.running = False

                    st.error(
                        f"Workflow error: {e}"
                    )


    # ========================================================
    # DISPLAY CASE
    # ========================================================

    case = st.session_state.case


    if case:

        st.markdown("---")


        st.subheader(
            f"Case {case['alert_id']} | "
            f"model: {case['model']}"
        )


        # ====================================================
        # TOP BUTTONS
        # ====================================================

        top_clear, top_cancel = st.columns(
            [1, 1]
        )


        with top_clear:

            if st.button(
                "Clear result",
                key="clear_result_top"
            ):

                clear_case()

                st.rerun()


        with top_cancel:

            if st.button(
                "Cancel execution",
                key="cancel_execution_top",
                disabled=not bool(
                    st.session_state.get(
                        "n8n_execution_id"
                    )
                )
            ):

                ok, message = cancel_n8n_execution()

                clear_case()


                if ok:

                    st.success(
                        message
                    )

                else:

                    st.warning(
                        message
                    )


                st.rerun()


        # ====================================================
        # CASE METRICS
        # ====================================================

        m1, m2, m3, m4 = st.columns(
            4
        )


        m1.metric(
            "Route",
            case.get(
                "route",
                "-"
            )
        )


        m2.metric(
            "Risk score",
            (
                case.get(
                    "risk_score"
                )
                if case.get(
                    "risk_score"
                ) is not None
                else "n/a"
            )
        )


        m3.metric(
            "System action",
            str(
                case.get(
                    "final_action",
                    "-"
                )
            ).upper()
        )


        m4.metric(
            "Queue",
            case.get(
                "queue",
                "-"
            )
        )


        # ====================================================
        # ROUTE MESSAGE
        # ====================================================

        if case.get(
            "route"
        ) == "EXCEPTION_ESCALATE":

            st.error(
                "EXCEPTION: "
                +
                "; ".join(
                    case.get(
                        "reasons",
                        []
                    )
                )
            )


        elif case.get(
            "route"
        ) == "INJECTION_HOLD":

            st.error(
                "Guardrail triggered: possible prompt "
                "injection in the free-text note. "
                "Held for review."
            )


        elif case.get(
            "escalate"
        ):

            st.warning(
                "ESCALATION: senior review required. "
                +
                "; ".join(
                    case.get(
                        "reasons",
                        []
                    )
                )
            )


        else:

            st.success(
                "Standard review. "
                +
                "; ".join(
                    case.get(
                        "reasons",
                        []
                    )
                )
            )


        # ====================================================
        # HALLUCINATION WARNING
        # ====================================================

        if case.get(
            "hallucination_flag"
        ):

            st.warning(
                "Quality flag: an agent cited a rule "
                "that was not in the evidence."
            )


        # ====================================================
        # RECOMMENDATION
        # ====================================================

        rec = case.get(
            "recommendation"
        )


        if rec:

            st.markdown(
                "### Recommendation"
            )


            if isinstance(
                rec,
                dict
            ):

                st.info(
                    rec.get(
                        "headline",
                        ""
                    )
                )


                a, b = st.columns(
                    2
                )


                with a:

                    st.markdown(
                        "**Key evidence**"
                    )


                    for x in rec.get(
                        "key_evidence",
                        []
                    ):

                        st.write(
                            "- "
                            +
                            str(x)
                        )


                with b:

                    st.markdown(
                        "**Suggested next steps**"
                    )


                    for x in rec.get(
                        "next_steps",
                        []
                    ):

                        st.write(
                            "- "
                            +
                            str(x)
                        )


                st.caption(
                    "Risk if wrong: "
                    +
                    str(
                        rec.get(
                            "risk_if_wrong",
                            ""
                        )
                    )
                )


            else:

                st.info(
                    str(rec)
                )


        # ====================================================
        # AGENT OUTPUTS
        # ====================================================

        findings = case.get(
            "agent_findings"
        )


        if findings:

            with st.expander(
                "Agent outputs (transparency)"
            ):

                for k, v in findings.items():

                    st.markdown(
                        f"**{k.title()} agent**"
                    )

                    st.json(
                        v
                    )


        # ====================================================
        # QUALITY / PERFORMANCE
        # ====================================================

        st.caption(
            f"Schema valid: "
            f"{case.get('schema_valid')} "
            f"| agent time: "
            f"{case.get('total_latency_s')} s "
            f"| wall time: "
            f"{st.session_state.get('elapsed', '-')} s"
        )


        # ====================================================
        # HUMAN-IN-THE-LOOP
        # ====================================================

        st.markdown("---")

        st.subheader(
            "Human decision (required)"
        )


        # ====================================================
        # ALREADY DECIDED
        # ====================================================

        if st.session_state.decided:

            d = st.session_state.decided


            st.success(
                f"Decision recorded: "
                f"{d.get('human_decision', '-')}"
                f" | outcome: "
                f"{d.get('final_outcome', '-')}"
            )


            st.write(
                "Audit comment: "
                +
                str(
                    d.get(
                        "human_comment",
                        ""
                    )
                )
            )


        # ====================================================
        # NO RESUME URL
        # ====================================================

        elif not st.session_state.resume_url:

            st.info(
                "No pending decision for this case."
            )


        # ====================================================
        # HUMAN DECISION FORM
        # ====================================================

        else:

            decision = st.radio(
                "Decision",
                [
                    "approve",
                    "reject",
                    "escalate"
                ],
                horizontal=True,
                help=(
                    "approve = accept the recommendation; "
                    "reject = override it; "
                    "escalate = send to supervisor"
                )
            )


            comment = st.text_area(
                "Comment (mandatory for approve / reject)"
            )


            # ------------------------------------------------
            # SUPERVISOR WARNING
            # ------------------------------------------------

            if (
                decision == "reject"
                and
                case.get(
                    "final_action"
                ) == "hold"
                and
                role != "supervisor"
            ):

                st.warning(
                    "Overriding a HOLD requires the "
                    "supervisor role. Submitting will "
                    "escalate instead."
                )


            # ------------------------------------------------
            # SUBMIT DECISION
            # ------------------------------------------------

            if st.button(
                "Submit decision",
                key="submit_human_decision"
            ):


                # ============================================
                # COMMENT VALIDATION
                # ============================================

                if (
                    decision != "escalate"
                    and
                    len(
                        comment.strip()
                    ) < 5
                ):

                    st.error(
                        "A comment of at least "
                        "5 characters is required."
                    )


                else:

                    try:

                        # ========================================
                        # VERIFY RESUME URL EXISTS
                        # ========================================

                        if not st.session_state.resume_url:

                            st.error(
                                "No active n8n resume URL is available."
                            )

                            st.stop()


                        # ========================================
                        # SUBMIT HUMAN DECISION TO N8N
                        # ========================================

                        decision_response = requests.post(
                            st.session_state.resume_url,
                            json={
                                "decision": decision,
                                "comment": comment,
                                "role": role
                            },
                            timeout=60
                        )


                        # ========================================
                        # IMPORTANT:
                        # CHECK N8N HTTP RESPONSE
                        # ========================================

                        if not decision_response.ok:

                            st.error(
                                "n8n did not accept the "
                                "human decision."
                            )

                            st.code(
                                f"HTTP {decision_response.status_code}\n\n"
                                f"{decision_response.text}"
                            )

                            st.stop()


                        # ========================================
                        # DECISION ACCEPTED
                        # ========================================

                        st.success(
                            f"Human decision '{decision}' "
                            f"submitted successfully to n8n."
                        )


                        # ========================================
                        # WAIT FOR N8N TO COMPLETE
                        # AND WRITE AUDIT
                        # ========================================

                        time.sleep(3)


                        # ========================================
                        # FETCH AUDIT LOG
                        # ========================================

                        audit_response = requests.get(
                            DATA_API + "/audit",
                            params={
                                "_t": time.time()
                            },
                            timeout=10
                        )


                        if not audit_response.ok:

                            st.warning(
                                "Decision was accepted by n8n, "
                                "but the audit log could not "
                                "be refreshed."
                            )

                            st.code(
                                f"HTTP {audit_response.status_code}\n\n"
                                f"{audit_response.text}"
                            )

                            st.stop()


                        rows = audit_response.json()


                        # ========================================
                        # FIND THIS ALERT'S AUDIT RECORD
                        # ========================================

                        mine = [
                            r
                            for r in rows
                            if r.get("alert_id")
                            == case["alert_id"]
                        ]


                        if mine:

                            # Most recent record for this alert
                            last = mine[-1]


                            st.session_state.decided = last

                            st.session_state.n8n_execution_id = None


                            st.success(
                                f"Decision recorded in audit log: "
                                f"{decision}"
                            )


                            # ------------------------------------
                            # Refresh the page so the decision
                            # appears permanently in the UI.
                            # ------------------------------------

                            time.sleep(1)

                            st.rerun()


                        else:

                            st.warning(
                                "Decision was accepted by n8n, "
                                "but the audit record has not "
                                "appeared yet."
                            )

                            st.info(
                                "Open the Audit log tab and "
                                "click Refresh."
                            )


                    # ============================================
                    # HITL ERROR HANDLING
                    # ============================================

                    except requests.exceptions.ConnectionError:

                        st.error(
                            "Could not reach the n8n resume URL. "
                            "Check that ngrok and the proxy are "
                            "still running."
                        )


                    except requests.exceptions.Timeout:

                        st.error(
                            "The HITL decision request timed out."
                        )


                    except Exception as e:

                        st.error(
                            f"Could not submit decision: {e}"
                        )


# ============================================================
# AUDIT LOG TAB
# ============================================================

with tab_audit:

    st.subheader(
        "Audit log"
    )


    # ========================================================
    # REFRESH BUTTON
    # ========================================================

    if st.button(
        "Refresh",
        key="refresh_audit"
    ):

        st.rerun()


    # ========================================================
    # LOAD AUDIT LOG
    # ========================================================

    try:

        audit_response = requests.get(
            DATA_API + "/audit",
            params={
                "_t": time.time()
            },
            timeout=10
        )


        audit_response.raise_for_status()


        rows = audit_response.json()


        if rows:

            audit_df = pd.DataFrame(
                rows
            )


            # --------------------------------------------
            # Sort newest first
            # --------------------------------------------

            if "logged_at" in audit_df.columns:

                audit_df = audit_df.sort_values(
                    "logged_at",
                    ascending=False
                )


            st.dataframe(
                audit_df,
                hide_index=True,
                use_container_width=True
            )


        else:

            st.info(
                "No decisions logged yet."
            )


    except Exception as e:

        st.error(
            "Audit log not reachable."
        )