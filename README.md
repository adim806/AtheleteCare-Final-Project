# AthleteCare Final Project

Monorepo for the course final project ([GitHub](https://github.com/adim806/AtheleteCare-Final-Project)).

Clone this repo and open the **repository root** in your editor (the folder that contains `Guardrails-Service/`, `RAG-Service/`, `Image-Analyser-Service/`, `LangGraph-Service/`, and `WebUI-Service/`).

Independent services (Python services use **their own** virtual environments; WebUI uses npm):

| Service | Folder | Runtime | Port |
|---------|--------|---------|------|
| Guardrails | `Guardrails-Service/` | `.venv311` | 8000 |
| RAG | `RAG-Service/` | `.venv` | 8001 |
| Image Analyser | `Image-Analyser-Service/` | `.venv` | 8002 |
| LangGraph Agent | `LangGraph-Service/` | `.venv` | 8003 |
| WebUI (React) | `WebUI-Service/` | `npm` | 8004 |

Do **not** use a shared root venv for Python services — dependencies differ and are installed per service.
<img width="2557" height="1265" alt="4" src="https://github.com/user-attachments/assets/2cf5253f-a015-413f-9dcd-cc3a5c21b614" />

<img width="2277" height="574" alt="5" src="https://github.com/user-attachments/assets/098b8c50-8999-4d7d-b78a-fd5dd4bcc261" />

---
<img width="1913" height="985" alt="3" src="https://github.com/user-attachments/assets/bfca2f7c-dbfe-4741-86bc-8ec4c0da9b59" />

<img width="1917" height="910" alt="צילום מסך 2026-08-10 135110" src="https://github.com/user-attachments/assets/8e9787bb-a098-4315-a1e1-f2ee741c48af" />

<img width="1913" height="984" alt="1" src="https://github.com/user-attachments/assets/34e62cd4-9ff8-4c46-a122-7059da0539d3" />

## First-time setup

### Guardrails
🔗 **[View Guardrails-Service Documentation](Guardrails-Service/README.md)**

```powershell
cd Guardrails-Service
py -3.11 -m venv .venv311
.\.venv311\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
# Edit .env and set OPENAI_API_KEY
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### RAG
🔗 **[View RAG-Service Documentation](RAG-Service/README.md)**

```powershell
cd RAG-Service
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
pip install -r requirements.txt
copy .env.example .env
# Place llama-3-8b-instruct.gguf in models/
python -m app.ingest
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### WebUI

```powershell
cd WebUI-Service
npm install
copy .env.example .env
# Set N8N_WEBHOOK_URL; ensure Ollama is running (ollama pull llama3)
npm run dev
```

See [WebUI-Service/README.md](WebUI-Service/README.md).

---

### Image-Analayser-Service

🔗 **[View Image-Analayser-Service Documentation](Image-Analayser-Service/README.md)**

### LangGraph-Service

🔗 **[View LangGraph-Service Documentation](LangGraph-Service/README.md)**


## Run both (two terminals)

**Terminal 1 — Guardrails**

```powershell
cd Guardrails-Service
.\.venv311\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

**Terminal 2 — RAG**

```powershell
cd RAG-Service
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8001
```

Or use the helper scripts from repo root:

```powershell
.\scripts\start-guardrails.ps1
.\scripts\start-rag.ps1
.\scripts\start-image-analyser.ps1
.\scripts\start-langgraph.ps1
.\scripts\start-webui.ps1
```

---

## Prompt engineering log (assignment §6)

See [`docs/Prompt Engineering Log/INDEX.md`](docs/Prompt%20Engineering%20Log/INDEX.md) — five graded surfaces + LangGraph tool-description log.

## Health checks

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe http://127.0.0.1:8001/health
curl.exe http://127.0.0.1:8002/health
curl.exe http://127.0.0.1:8003/health
# WebUI (open in browser)
start http://127.0.0.1:8004
```
