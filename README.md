# AthleteCare Final Project

Monorepo for the course final project ([GitHub](https://github.com/adim806/AtheleteCare-Final-Project)).

Clone this repo and open the **repository root** in your editor (the folder that contains `Guardrails-Service/`, `RAG-Service/`, `Image-Analyser-Service/`, `LangGraph-Service/`, and `WebUI-Service/`).

<img width="2507" height="1052" alt="Image-Analyse-Test-Response" src="https://github.com/user-attachments/assets/912430d2-5872-4aa0-bad9-0dabb3a2b290" />


---

## Project Overview
**AthleteCare** is an AI-driven **clinical decision support** and knowledge management system designed for professional football club medical department. The platform streamlines the handling of player injury reports by automatically extracting clinical data, analyzing medical imaging (e.g., X-rays), and retrieving relevant club protocols. It uses a dynamic AI agent to evaluate severity and generate structured, markdown-formatted clinical briefs, routing urgent cases to the appropriate medical and management staff in real time.

## ⚙️ n8n Orchestration 
*Note: Not stored as application code in this repository, but central to the Submit report process.*
<img width="2277" height="574" alt="5" src="https://github.com/user-attachments/assets/098b8c50-8999-4d7d-b78a-fd5dd4bcc261" />
**Workflow Execution:**
1. **Webhook:** Receives body from `WebUI`.
2. **Guardrails Input Check:** Validates incoming requests.
3. **Information Extractor:** Extracts structured fields (including `question_type`).
4. **AI Agent:** Routes to the correct backend tool(s).
5. **Report Writer:** Generates a structured JSON + markdown report.
6. **Guardrails Output Check:** Ensures safety and compliance.
7. **Route & Respond:** Determines route (urgent/routine), handles optional Gmail notifications, and responds via Webhook to the `WebUI`.

> **💡 Tip:** Use a published production webhook URL in `WebUI-Service/.env` (`N8N_WEBHOOK_URL`), not only `webhook-test`, unless the workflow is actively listening in test mode.

## System Architecture & Information Flow
The project is built as a Monorepo containing several independent microservices. The core workflow is orchestrated by **n8n**, which receives injury reports via webhook, validates them, and routes requests to the relevant AI services. 


### Core Services
The repository consists of the following isolated services, each responsible for a specific domain in the triage pipeline:

 **1. Guardrails Service (Port 8000):** Acts as the safety layer. It validates incoming webhook payloads to ensure they contain legitimate medical reports (filtering out spam) and verifies the final generated clinical briefs to ensure they meet strict medical safety guidelines before distribution.
* **Purpose:** Safety layer before and after LLM-generated content in the n8n workflow.
* **Tech:** FastAPI, NVIDIA NeMo Guardrails, OpenAI (for rail self-checks where configured).
* **Endpoints:** GET /health, POST /check/input, POST /check/output.
* **In the pipeline:** First gate after the webhook; final gate after the Report Writer. Failed input → reject; output → safe_text for routing and emails.

Details:  🔗 **[View Guardrails-Service Documentation](Guardrails-Service/README.md)**
  
 **2. RAG Service (Port 8001):** The club's internal knowledge base. It uses Retrieval-Augmented Generation to search and retrieve historical injury precedents, specific club protocols, and Return-to-Play (RTP) guidelines based on the player's clinical description.

* **Purpose:** Retrieval-augmented generation over club Markdown data (PROT-*, CASE-*, POL-*) under data/.
* **Tech:** FastAPI, ChromaDB, LangChain, sentence-transformers/all-MiniLM-L6-v2, llama-cpp-python (local GGUF).
* **Flow** Offline python -m app.ingest → online POST /query with { "description": "..." } → retrieve, filter, augment, generate with citations.
* **In the pipeline:** Called directly when routing is knowledge-only; also called by LangGraph for multi-step cases.

Details: 🔗 **[View RAG-Service Documentation](RAG-Service/README.md)**
  
 **3. Image Analyser Service (Port 8002):** The computer vision component. It analyzes attached clinical images (like X-rays) to determine the injured body region, assign a condition severity score, and provide a confidence metric to assist the triage agent.

* **Purpose:** X-ray triage from { "image_url": "..." } — region, normal vs fracture-like proxy score, confidence, and imaging_reliable.
* **Tech:** FastAPI, PyTorch, dual-head ResNet-50, radiograph validation heuristics.
* **Note**  condition_score (1 / 5) is an imaging proxy, not a final diagnosis or RTP grade.
* **In the pipeline:**  Direct call for imaging-only; internal call from LangGraph for multi-step.

Details: 🔗 **[View Image-Analayser-Service Documentation](Image-Analayser-Service/README.md)**
  
 **4. LangGraph Agent Service (Port 8003):** The complex reasoning engine. Used for "multi-step" cases that require both imaging triage and club protocol retrieval. It coordinates calls to multiple tools in a single chain to synthesize a comprehensive clinical assessment.
 
* **Purpose:** Stateful multi-step agent — plan → execute tools over HTTP → synthesise one answer.
* **Tech:** FastAPI, LangGraph (StateGraph), OpenAI (planner + synthesiser when configured), httpx to RAG and Image Analyser.
* **Graph**  planner → tool_execution → synthesiser → END.
* **Endpoint**  POST /agent/run with { "query", "image_url?" } → { "answer", "tools_used", "reasoning_steps" }.
* **In the pipeline:**  n8n AI Agent should call only this service for multi_step (LangGraph invokes Image + RAG internally; avoids duplicate tool loops from n8n).
  
Details: 🔗 **[View LangGraph-Service Documentation](LangGraph-Service/README.md)**
  
 **5. WebUI Service (Port 8004):** A React-based frontend application that provides a user-friendly interface for medical staff to submit injury reports and view the system's analysis.

* **Purpose:** Professional ChatGPT-style UI for local assistant chat and triage submission.
* **Tech:** Vite, React, TypeScript, Tailwind, framer-motion, local conversation storage (sql.js), Vite proxies for Ollama and n8n.
* **Tabs**   Assistant (Ollama + PE-log system prompt), Submit report (n8n webhook, long timeout for full workflow).
* **Course note:**  Guidelines suggest Gradio/Streamlit; this repo uses React for UX and monorepo maintenance with the same integrations.

Details: 🔗 **[View WebUI-Service Documentation](WebUI-Service/README.md)**

---

## 🛠️ Technology Summary

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React, TypeScript, Vite, Tailwind CSS, framer-motion |
| **Local Chat** | Ollama |
| **Orchestration** | n8n, OpenAI *(Extractor, Agent, Report Writer in workflow)* |
| **Safety** | NVIDIA NeMo Guardrails |
| **RAG** | ChromaDB, LangChain, sentence-transformers, llama-cpp-python |
| **Vision** | PyTorch, ResNet-50 |
| **Agent** | LangGraph, httpx |
| **APIs** | FastAPI, Uvicorn, Pydantic |
| **Local Dev** | PowerShell scripts in `scripts/`, per-service `.env` |

---

## 📐 Design Principles

| Principle | How it is implemented |
| :--- | :--- |
| **Microservices** | One folder, one virtual environment (venv), one port per Python service. |
| **API-first** | FastAPI contracts; n8n integrates via HTTP. |
| **Local-first privacy** | RAG embeddings/LLM and Ollama chat on-premises. |
| **Hybrid cloud** | OpenAI in n8n for orchestration; optional OpenAI in Guardrails/LangGraph. |
| **Safety** | Guardrails on input/output; imaging reliability gates; clinical disclaimers in UI. |
| **Observability** | n8n execution logs, LangGraph `reasoning_steps`, `/health` on each service. |

---

## 🎯 What the Project Demonstrates
- **End-to-end injury triage:** From WebUI through n8n to a structured clinical report.
- **Combined capabilities:** RAG + medical imaging + multi-step agent with explicit routing rules.
- **Comprehensive safety measures:** Guardrails applied on both user input and model output.
- **Documented prompt engineering:** Detailed across n8n, Ollama, and LangGraph tool descriptions.
- **Modular architecture:** Each service can be run, tested, and health-checked independently.

---

## Setup & Execution

Clone this repo and open the **repository root** in your editor (the folder that contains `Guardrails-Service/`, `RAG-Service/`, `Image-Analyser-Service/`, `LangGraph-Service/`, and `WebUI-Service/`).

Independent services (Python services use **their own** virtual environments; WebUI uses npm). 
**Click on the service name below to view its specific documentation:**

| Path | Role |
|---------|--------|
| Assistant | `Local chat with Ollama—explains the system, protocols, and pipeline; not the full n8n triage flow.` |
| Submit report | `Sends JSON to the n8n webhook; runs the full triage workflow and displays the returned clinical report.` |


| Service | Folder | Runtime | Port |
|---------|--------|---------|------|
| [Guardrails](Guardrails-Service/README.md) | `Guardrails-Service/` | `.venv311` | 8000 |
| [RAG](RAG-Service/README.md) | `RAG-Service/` | `.venv` | 8001 |
| [Image Analyser](Image-Analyser-Service/README.md) | `Image-Analyser-Service/` | `.venv` | 8002 |
| [LangGraph Agent](LangGraph-Service/README.md) | `LangGraph-Service/` | `.venv` | 8003 |
| [WebUI (React)](WebUI-Service/README.md) | `WebUI-Service/` | `npm` | 8004 |

Do **not** use a shared root venv for Python services — dependencies differ and are installed per service.

## N8N Workflow

<img width="2557" height="1065" alt="4" src="https://github.com/user-attachments/assets/2cf5253f-a015-413f-9dcd-cc3a5c21b614" />

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
🔗 **[View WebUI-Service Documentation](WebUI-Service/README.md)**

```powershell
cd WebUI-Service
npm install
copy .env.example .env
# Set N8N_WEBHOOK_URL; ensure Ollama is running (ollama pull llama3)
npm run dev
```

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
<img width="2507" height="1052" alt="Image-Analyse-Test-Response" src="https://github.com/user-attachments/assets/65c932da-51c4-474a-bba8-5fc461044d68" />
<img width="1108" height="1104" alt="Image-Analyse-Test-health" src="https://github.com/user-attachments/assets/6e59d24f-d25f-478d-89dd-bfa0a7dd8ceb" />



```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe http://127.0.0.1:8001/health
curl.exe http://127.0.0.1:8002/health
curl.exe http://127.0.0.1:8003/health
# WebUI (open in browser)
start http://127.0.0.1:8004
```
