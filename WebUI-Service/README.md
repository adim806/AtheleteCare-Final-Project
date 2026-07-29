# AthleteCare WebUI Service

React frontend for guideline **§5 WebUI + Ollama** (assignment Layer 1).

| | |
|--|--|
| Stack | Vite · React 18+ · TypeScript |
| Port | **8004** |
| Tabs | **Assistant** (local Ollama) · **Submit report** (n8n webhook) |

## Rubric note (Gradio / Streamlit deviation)

The course guideline suggests Gradio or Streamlit. This service implements the **same two surfaces and integrations** in React for a clearer AthleteCare UI and easier monorepo maintenance. Chat still uses local Ollama with the PE-log system prompt; submission still POSTs to the n8n webhook and displays the returned report.

## Prerequisites

1. **Node.js 18+**
2. **Ollama** installed and running: https://ollama.ai  
   ```powershell
   ollama pull llama3
   ollama serve
   ```
3. **n8n** workflow active with a production/test webhook URL
4. Backend services + tunnels as needed for your live n8n flow

## Setup

```powershell
cd WebUI-Service
npm install
copy .env.example .env
# Edit .env — set N8N_WEBHOOK_URL to your n8n webhook
npm run dev
```

Open http://127.0.0.1:8004

Or from repo root:

```powershell
.\scripts\start-webui.ps1
```

## Environment

| Variable | Where used | Purpose |
|----------|------------|---------|
| `VITE_OLLAMA_MODEL` | Browser | Ollama model name (default `llama3`) |
| `OLLAMA_URL` | Vite proxy | Ollama base (default `http://127.0.0.1:11434`) |
| `N8N_WEBHOOK_URL` | Vite proxy | Full webhook URL for `POST /api/triage` |

Restart `npm run dev` after changing `.env` (proxy reads env at startup).

## API wiring (CORS-safe)

```text
Browser  →  POST /api/ollama/api/chat  →  Ollama /api/chat
Browser  →  POST /api/triage           →  N8N_WEBHOOK_URL
```

### Submit payload

```json
{
  "text": "<clinical report>",
  "image_urls": ["https://..."],
  "agent_name": "optional physio name"
}
```

Matches the Information Extractor input (`body.text` + `body.image_urls`). Client waits up to **10 minutes** for n8n to finish.

### Chat

Uses the final system prompt from `docs/Prompt Engineering Log/Ollama.md` (`src/prompts/ollamaSystem.ts`).

## Scripts

| Command | Action |
|---------|--------|
| `npm run dev` | Dev server on :8004 with proxies |
| `npm run build` | Typecheck + production build |
| `npm run preview` | Preview build on :8004 (proxies are dev-only — use `dev` for demos) |

For graded demos, prefer **`npm run dev`** so Ollama/n8n proxies work.
