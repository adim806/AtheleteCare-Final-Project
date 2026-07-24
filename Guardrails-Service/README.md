# Guardrails Service

NeMo Guardrails FastAPI service for AthleteCare input/output safety checks.

## Setup (Python 3.11)

```powershell
cd Guardrails-Service
py -3.11 -m venv .venv311
.\.venv311\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Set `OPENAI_API_KEY` in `.env`.

## Run

```powershell
.\.venv311\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

From repo root: `.\scripts\start-guardrails.ps1`

## Endpoints

- `GET /health`
- `POST /check/input` — `{ "text": "..." }` → `{ "pass", "reason" }`
- `POST /check/output` — `{ "text": "..." }` → `{ "pass", "reason", "safe_text" }`

Uses **`.venv311` in this folder only** — not a shared monorepo venv.
