# Governed Agentic AI -- Fraud Investigation Console

A Streamlit proof-of-concept UI for a governed agentic AI
fraud-investigation workflow.

> **Academic/demo use:** The application uses synthetic fraud-alert
> data. The AI recommends; the investigator makes the final decision.

## Features

-   Fraud-alert selection and investigation
-   AI model selection
-   n8n-based agentic orchestration
-   Risk score, route, action and queue display
-   Recommendation and evidence display
-   Agent-output transparency
-   Hallucination/quality flags
-   Human-in-the-loop approval, rejection and escalation
-   Investigator/supervisor role governance
-   Audit-log viewing

## Architecture

``` text
User / Professor
       |
       v
Streamlit UI
       |
       +--------------------+
       |                    |
       v                    v
   Data API               n8n
   Port 8000            Port 5678
                            |
                            v
                         Ollama
                       Port 11434
```

The current UI expects the backend services to be reachable at their
configured addresses.

## Project Structure

``` text
project/
├── ui/
│   └── app.py
├── requirements.txt
└── README.md
```

## Requirements

Python 3.10+ is recommended.

Install the Python dependencies:

``` powershell
pip install -r requirements.txt
```

## Run Locally

From the project root:

``` powershell
python -m venv venv
.env\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run ui/app.py
```

The UI normally opens at:

``` text
http://localhost:8501
```

## Backend Services

The complete application currently requires:

-   **Data API:** `http://127.0.0.1:8000`
-   **n8n:** `http://localhost:5678`
-   **n8n webhook:** `http://localhost:5678/webhook/fraud-alert`
-   **Ollama:** `http://localhost:11434`

The n8n fraud-investigation workflow must be active.

## Human-in-the-Loop Governance

The UI supports:

-   Investigator
-   Supervisor

Available decisions:

-   Approve
-   Reject
-   Escalate

Approve/reject decisions require a comment. A HOLD recommendation
requires supervisor authority to override.

This keeps the final decision with a human reviewer rather than allowing
the AI to act autonomously.

## Audit Log

The Audit Log tab displays decisions retrieved from the Data API and
provides traceability for the investigation and human review process.

## Deployment

### Streamlit Community Cloud

The UI can be deployed through Streamlit Community Cloud.

Set the application entry point to:

``` text
ui/app.py
```

The repository should contain at least:

``` text
ui/app.py
requirements.txt
README.md
```

### Important: Backend Limitation

The current application uses local backend addresses such as:

``` text
http://127.0.0.1:8000
http://localhost:5678
```

A Streamlit Cloud application cannot access services running on
`localhost` on your laptop.

Therefore, deploying only the Streamlit UI gives you a public UI but
does **not** automatically make n8n, the Data API or Ollama available to
that public application.

For a fully public demonstration, the backend services must also be
hosted or exposed through a secure architecture, and the UI must use the
corresponding public backend URLs.

Do not expose n8n, Ollama or internal APIs publicly without appropriate
authentication and security controls.

## Models

The project evaluates local Ollama models including:

-   Qwen2.5:3B
-   Llama3.2:3B
-   Gemma2:2B

## Security Notes

-   Do not commit API keys, passwords or authentication tokens.
-   Do not commit `.env` files containing secrets.
-   Do not expose n8n or Ollama directly to the public internet without
    security controls.
-   Use synthetic data for academic demonstrations.
-   Review all backend URLs before deployment.

## Academic Scope

This proof of concept demonstrates:

-   Multi-agent orchestration
-   Evidence-based transaction analysis
-   Customer behaviour analysis
-   Rule-based risk scoring
-   Policy/recommendation generation
-   Prompt-injection guardrails
-   Hallucination detection
-   Human-in-the-loop governance
-   Role-based override controls
-   Auditability

## License

Academic proof-of-concept. Not intended for production financial or
fraud-decisioning use.
