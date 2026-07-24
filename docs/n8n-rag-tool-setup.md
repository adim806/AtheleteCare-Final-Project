# Wire RAG Service into n8n AI Agent

This connects the AthleteCare **RAG-Service** (`POST /query`) as the `rag_service` tool used by the n8n AI Agent.

## Prerequisites

1. RAG running locally on **port 8001** (Guardrails stays on 8000). From repo root:

```powershell
.\scripts\start-rag.ps1
```

Or manually:

```powershell
cd RAG-Service
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

2. Expose it for n8n.cloud with a **second** public tunnel (do **not** reuse the Guardrails ngrok domain on 8000).

```powershell
ngrok http 8001
```

If your free ngrok account already has one online endpoint, use Cloudflare Tunnel instead (install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/) so `cloudflared` is on your PATH):

```powershell
cloudflared tunnel --url http://127.0.0.1:8001 --no-autoupdate
```

Copy the printed HTTPS URL, e.g. `https://<random>.trycloudflare.com` or your ngrok host.

3. Confirm health:

```text
GET https://<your-rag-public-host>/health
```

Expect `chroma_db_exists: true` and `model_exists: true`.

Tunnel URLs are ephemeral — restart regenerates them. Update the n8n tool URL each time (or use a reserved ngrok domain).

---

## n8n AI Agent tool setup

Add / configure an **HTTP Request Tool** attached to the **AI Agent** node:

| Setting | Value |
|--------|--------|
| Tool Name | `rag_service` |
| Description | Search club medical cases and protocols. Use for historical precedents, rehab protocols, and evidence-based clinical insight. Input: injury description text. |
| Method | `POST` |
| URL | `https://<your-rag-public-host>/query` |
| Send Body | On |
| Body Content Type | JSON |
| Body | see below |

### JSON body (tool parameter mapping)

Prefer a single tool argument `description` mapped to the body:

```json
{
  "description": "{{ $fromAI('description', 'Full injury description or clinical query text to search against club medical records') }}"
}
```

If your n8n version uses fixed fields instead of `$fromAI`:

```json
{
  "description": "{{ $json.output.injury_type }} pain at {{ $json.output.injury_location }}, player {{ $json.output.player_name }}, pain level {{ $json.output.pain_level }}. Original report: {{ $('Injury Report Webhook1').item.json.body.report_text }}"
}
```

### Expected response schema

```json
{
  "similar_listings": ["[1] ...", "[2] ...", "[3] ..."],
  "insight": "Based on Document 1 ..."
}
```

Agent system prompt already says: **ALWAYS execute the rag_service tool** — keep that instruction.

---

## Isolated smoke test (optional webhook)

Same pattern as Guardrails output testing:

1. Webhook path: `athletecare-rag-test`
2. Respond: Immediately
3. HTTP Request → `POST https://<rag>/query`
4. Body field `description` = `{{ $json.body.description }}`

Postman body:

```json
{
  "description": "Player reports sharp pain in posterior calf during sprinting, unable to continue training."
}
```

---

## Port map (local)

| Service | Port |
|---------|------|
| Guardrails-Service | 8000 |
| RAG-Service | 8001 |

Do not run both on 8000.
