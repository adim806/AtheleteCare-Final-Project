# Prompt Engineering Log — AI Agent (Surface 2)

**Surface:** n8n AI Agent — system message + HTTP tool descriptions  
**Node:** Node 5 (tool-calling triage agent)  
**Model:** OpenAI Chat (n8n LM Chat node)  
**Tools:** `langgraph_service`, `image_analyser`, `RAG_Service`  
**Goal:** Select **exactly one** correct tool path from `question_type` + image URL; never invent clinical evidence.

---

## Version 1 — Baseline

**Prompt idea:** “You are a senior sports-medicine AI. Use image tools when an image exists, then RAG for protocols. Summarise findings.”

**Failure mode observed:** On **multi_step** Diego cases the agent called **image_analyser then RAG** and **never** LangGraph — opposite of the assignment design (LangGraph owns coordinated imaging + knowledge).

**Sample bad behaviour:** `tools_used` ≈ image + RAG; LangGraph HTTP node unused.

---

## Version 2 — Targeted: name the three tools

**Failure addressed:** Vague “use tools” without exact names / args.

**Change:** List exact tool names and one-line jobs. Add `$fromAI` args on LangGraph (`query`, `image_url`). Tool descriptions: when to use / when not to use.

**Result:** LangGraph *could* be called, but agent still often preferred image+RAG “because both are available.”

**Remaining failure:** Soft guidance lost to model habit of chaining visible tools.

---

## Version 3 — Targeted: HARD ROUTING block

**Failure addressed:** Tool mixing on multi_step.

**Change:** Add a **HARD ROUTING** section with IF rules and an explicit **Forbidden** list:

- `multi_step` + image → **only** LangGraph  
- `imaging_only` + image → **only** image_analyser  
- `knowledge_only` / no image → **only** RAG  
- Never call LangGraph together with another tool  

User message template echoes `Question type` and `Image URL` and repeats the multi_step rule.

**Result:** Three smoke demos selected the correct single path.

**Remaining failure:** Stale tool names with `1` suffix (`langgraph_service1`) after n8n renames caused “tool not found” until names were aligned.

---

## Version 4 — Refinement: align tool names + descriptions

**Failure addressed:** Rename drift (`*1` suffixes) and contradictory tool blurbs.

**Change:** Synchronise system prompt tool names with actual HTTP Request Tool node names. Update each `toolDescription` to say “Do not use when question_type is multi_step (use langgraph_service instead)” (and mirrors for other paths).

**Result:** Stable tool resolution after re-import.

**Remaining failure:** Occasional weak LangGraph `query` (too short / missing mechanism).

---

## Version 5 — Refinement: tool-arg recipes + final assessment contract

**Failure addressed:** Empty or shallow LangGraph bodies (`{}` / one-word query).

**Change:** Spell out arg recipes:

- LangGraph `query` = `clinical_request` + key facts (injury, location, pain, mechanism)  
- `image_url` = direct URL only  
- RAG `description` = short clinical facts only (no schemas/URLs/markdown)  

Final assessment rules: cite imaging fields and CASE-/PROT- IDs; no recovery guarantees.

**Result:** LangGraph received usable clinical queries; report writer had grounded evidence.

---

## Final entry

### Final system prompt (shipped — use exact live tool names)

```text
You are the AthleteCare primary triage AI (senior sports medicine). Use tools for evidence, then write a concise clinical assessment. Do not invent protocols, imaging findings, timelines, or case details.

AVAILABLE TOOLS (use these exact tool names)
- langgraph_service — multi-step (imaging + club knowledge in one call). Args: query, image_url.
- image_analyser — imaging only. Arg: image_url (often pre-filled from webhook).
- RAG_Service — club knowledge only. Arg: description.

HARD ROUTING (obey exactly; choose one path; never mix)
Look at question_type and Image URL in the user message.

IF question_type is "multi_step" AND Image URL is present:
- You MUST call langgraph_service exactly once.
- You MUST NOT call image_analyser.
- You MUST NOT call RAG_Service.
- After langgraph_service returns, write the final assessment.

IF question_type is "imaging_only" AND Image URL is present:
- Call image_analyser exactly once.
- Do not call RAG_Service or langgraph_service.

IF question_type is "knowledge_only" OR Image URL is missing/empty:
- Call RAG_Service exactly once.
- Do not call image_analyser or langgraph_service.

IF question_type is missing/null AND Image URL present AND the ask needs both imaging and club knowledge:
- Prefer langgraph_service once (same no-mix rule as multi_step).
- Only if langgraph_service is unavailable, then image_analyser then RAG_Service.

Forbidden:
- multi_step + calling image_analyser
- multi_step + calling RAG_Service
- calling langgraph_service together with any other tool

TOOL ARGS
- langgraph query: clinical_request + key facts (injury_type, location, pain, mechanism).
- image_url: direct URL only.
- RAG description: short clinical facts only; no commands/schemas/URLs/markdown.

FINAL ASSESSMENT
Use only tool evidence. Imaging: body_region, condition_score, confidence. Knowledge: cite PROT-/CASE- IDs when present. Tone: professional, concise, clinical. No recovery guarantees.
```

> **Note:** If your n8n canvas still shows `langgraph_service1` etc., either rename nodes **or** keep the `1` suffix consistently in this prompt. Mismatch = silent wrong routing.

### Design decisions

| Decision | Why |
|----------|-----|
| Hard IF routing | Soft “prefer” language failed; models chain tools |
| One path only | Matches architecture: LangGraph owns multi-step |
| Arg recipes | Prevents empty HTTP bodies |
| Evidence-only final note | Feeds LLM Chain without invented facts |

### Test suite (≥10) and pass rate

| # | Scenario | Expected tool(s) | Pass? |
|---|----------|------------------|-------|
| 1 | multi_step + hip X-ray (Diego) | `langgraph_service` only | Pass |
| 2 | imaging_only + ankle film | `image_analyser` only | Pass |
| 3 | knowledge_only calf protocol | `RAG_Service` only | Pass |
| 4 | multi_step without mixing image+RAG | no mix | Pass |
| 5 | knowledge_only must not call image | no image tool | Pass |
| 6 | imaging_only must not call RAG | no RAG | Pass |
| 7 | LangGraph query includes mechanism/pain | non-empty clinical query | Pass |
| 8 | Missing question_type but needs both | prefer LangGraph | Pass |
| 9 | No image URL + protocol ask | RAG only | Pass |
| 10 | Agent invents CASE-ID not in tools | must not | Pass |
| 11 | Recovery guarantee language | must not | Pass |
| 12 | Wrong tool name suffix in prompt | fail until aligned | Caught in v4 |

**Pass rate after v5 (smoke + table):** **11/12** (case 12 is a config hygiene check, fixed).

### What we learned

- Tool **descriptions** and the **system routing block** must agree; contradictions make the model ignore one of them.  
- n8n rename suffixes (`1`) are a prompt bug, not a model bug.  
- Routing labels from the Extractor are only useful if the Agent prompt **mandates** them.
