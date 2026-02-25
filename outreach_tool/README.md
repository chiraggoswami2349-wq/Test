# Cybernara Internal Outreach Tool

Internal Streamlit-based tool to verify and send B2B outreach emails through Microsoft 365 Graph with sender allow-list controls, business-hour checks by country, and detailed CSV logs.

## Features
- Upload CSV/Excel and run campaign with one click.
- Optional Verifalia verification (`Standard`, `High`, `Extreme`).
- Tries `email1` -> `email2` -> `email3`; sends only once using first sendable email.
- Country-aware business-hour gate (Mon-Fri, 09:00-18:00 local time).
- Sender allow-list enforcement.
- Microsoft Graph token caching + automatic refresh on expiry / 401.
- Retry handling for Graph `429` and `5xx` responses.
- Exportable per-run log in `output/outreach_log_YYYYMMDD_HHMM.csv`.

## Project structure

```text
outreach_tool/
  app.py
  run_campaign.py
  requirements.txt
  config.py
  services/
    graph_client.py
    verifalia_client.py
    timezone_rules.py
    templating.py
    logger.py
  sample/
    leads_sample.csv
  output/
  .env.example
```

## Setup

```bash
cd outreach_tool
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env`:
- `TENANT_ID`
- `CLIENT_ID`
- `CLIENT_SECRET`
- `VERIFALIA_USERNAME` (only needed if verification ON)
- `VERIFALIA_PASSWORD` (only needed if verification ON)

## Run Streamlit app

```bash
cd outreach_tool
streamlit run app.py
```

The Streamlit panel also includes live operator logs such as Verifalia checks, send attempts, successful sends, and enforced delays.

## Optional CLI mode

```bash
cd outreach_tool
python run_campaign.py --input sample/leads_sample.csv --verify --quality High --max 50
```

## Input columns (CSV or Excel)
Required:
- `name`
- `company`
- `sender`
- `country`
- `subject`
- `body`
- `email1`

Optional:
- `email2`
- `email3`

Supported placeholders in `subject` and `body`:
- `{{name}}`
- `{{company}}`
- `{{sender}}`
- `{{country}}`

## Business hours and country map
- India → `Asia/Kolkata`
- Australia → `Australia/Melbourne`
- UAE → `Asia/Dubai`
- UK → `Europe/London`
- USA → `America/New_York`

Unknown country is skipped as `Invalid_Country`.

## Notes
- Secrets are loaded from environment variables / `.env`; no secrets are hardcoded.
- Access tokens are never printed or logged.
- Content sends as plain text by default.
