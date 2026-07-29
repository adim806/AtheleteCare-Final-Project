# Prompt Engineering Log — AthleteCare

**Course deliverable:** Section 6 of the Final Project Guideline (25% of grade).  
**Domain adaptation:** AI Property Triage → **AthleteCare** sports-medicine triage (same architecture).

## Graded surfaces (5)

| # | Surface | Log file | Component |
|---|---------|----------|-----------|
| 1 | n8n Information Extractor | [Information_Extractor.md](./Information_Extractor.md) | Node 4 — `systemPromptTemplate` + attribute definitions |
| 2 | n8n AI Agent | [AI_Agent.md](./AI_Agent.md) | Node 5 — agent system prompt + tool descriptions |
| 3 | LangChain RAG Retrieval | [RAG.md](./RAG.md) | Service 1 — context injection / citation prompt |
| 4 | Guardrails Rail Prompts | [Guardrails.md](./Guardrails.md) | Service 3 — input + output self-check prompts |
| 5 | Local Ollama System Prompt | [Ollama.md](./Ollama.md) | WebUI — AthleteCare assistant grounding / refusals |

## Related (Service 4 requirement)

| Surface | Log file | Notes |
|---------|----------|-------|
| LangGraph tool descriptions | [LangGraph.md](./LangGraph.md) | §4.4 — planner tool-selection prompts (not one of the five graded rows, still required) |

## Shared method

For each surface we followed the guideline format:

1. **Version 1** — baseline prompt, run on test cases, record failures  
2. **Versions 2–3** — targeted fixes for one failure mode each  
3. **Versions 4–5** — refinement  
4. **Final entry** — ship prompt + design rationale + pass rate on ≥10 cases  

Test cases are AthleteCare-specific (injury reports, imaging + protocols, spam, injections, off-topic chat).

## Final prompts live in

| Surface | Code / config location |
|---------|------------------------|
| Extractor / AI Agent | n8n export `28jul1345.json` (or latest AthleteCare workflow) |
| RAG | `RAG-Service/app/main.py` → `prompt_template` |
| Guardrails | `Guardrails-Service/config/prompts.yml` |
| LangGraph | `LangGraph-Service/app/prompts.py` |
| Ollama | `WebUI-Service/src/prompts/ollamaSystem.ts` |
