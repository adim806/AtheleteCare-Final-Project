# Prompt Engineering Log — LangGraph Tool Descriptions (Service 4)

**Surface:** LangGraph planner tool descriptions + planner/synthesiser system prompts  
**Component:** `LangGraph-Service/app/prompts.py` (`TOOL_DESCRIPTIONS_VERSION`)  
**Endpoint:** `POST /agent/run`  
**Goal:** Planner selects the right tool(s) — `image_analyser`, `rag_service`, or both — without inventing tool names or skipping needed evidence.  
**Note:** Not one of the five graded PE surfaces in §6, but required by §4.4 (iterate ≥5 times on tool descriptions).

---

## Version 1 — Baseline

**Prompt idea:** Short blurbs: “RAG searches documents. Image tool looks at pictures.”

**Failure mode observed:** Planner called RAG for “what does this X-ray show?” and skipped imaging when `image_url` was present. Sometimes invented tool names (`xray_tool`).

---

## Version 2 — Targeted: exclusive Do/Don’t per tool

**Failure addressed:** Wrong tool for modality.

**Change:** Each tool description states **Call when** and **Do NOT use for**. Image tool lists return fields (`body_region`, `condition_score`, `confidence`). RAG lists cases/protocols/RTP.

**Result:** Fewer cross-calls on single-intent queries.

**Remaining failure:** Multi-step questions often picked only one tool.

---

## Version 3 — Targeted: multi-step → both tools, imaging first

**Failure addressed:** Incomplete plans on “imaging + protocol” questions.

**Change:** Planner rules: if both needed, include **both**; prefer `image_analyser` **before** `rag_service`; drop image tool if no URL; JSON-only plan schema.

**Result:** Diego-style multi-step plans returned `["image_analyser", "rag_service"]`.

**Remaining failure:** Vague “help with this injury” without URL sometimes still requested image_analyser.

---

## Version 4 — Refinement: URL gate in planner rules

**Failure addressed:** Planning image tool with no URL.

**Change:** Explicit: include `image_analyser` only when `image_url` is provided **and** question involves imaging/severity/region.

**Result:** Knowledge-only queries planned RAG alone.

**Remaining failure:** Synthesiser occasionally invented CASE IDs not in tool results.

---

## Version 5 — Refinement: synthesiser evidence contract + version tag

**Failure addressed:** Ungrounded synthesis.

**Change:** Strengthen `SYNTHESISER_SYSTEM`: use only tool results; cite IDs when present; mention imaging triad fields; uncertainty note if thin evidence. Bump `TOOL_DESCRIPTIONS_VERSION` when descriptions change (for the assignment log).

**Result:** Answers stayed tied to tool payloads in smoke tests.

---

## Final entry

### Final tool descriptions (shipped)

See `LangGraph-Service/app/prompts.py` — `TOOL_RAG_SERVICE`, `TOOL_IMAGE_ANALYSER`, `PLANNER_SYSTEM`, `SYNTHESISER_SYSTEM` (`TOOL_DESCRIPTIONS_VERSION = "v1"` at ship; bump when you edit).

**Design decisions**

| Decision | Why |
|----------|-----|
| Dual Call when / Do NOT | Planner is description-driven |
| Imaging before RAG | Severity context before protocol retrieval |
| JSON-only plan | Reliable parsing in `llm.py` |
| Synthesiser “only tool results” | Stops CASE-ID hallucination |

### Benchmark queries (10) — planner selection

| # | Query theme | image_url? | Expected tools | Pass? |
|---|-------------|------------|----------------|-------|
| 1 | Hip X-ray + urgent management + RTP | yes | both (image→RAG) | Pass |
| 2 | What region/severity is this film? | yes | image only | Pass |
| 3 | Grade 2 calf protocol? | no | RAG only | Pass |
| 4 | Ankle film + similar club cases | yes | both | Pass |
| 5 | Concussion RTP policy | no | RAG only | Pass |
| 6 | Condition score only | yes | image only | Pass |
| 7 | Hamstring + protocols, no image | no | RAG only | Pass |
| 8 | Multi-step knee + MRI ask + cases | yes | both | Pass |
| 9 | Empty/irrelevant tool name temptation | yes | only catalog tools | Pass |
| 10 | Imaging question without URL | no | RAG or empty imaging; **not** image | Pass |

**Pass rate:** **10/10** on planner selection for this suite (with OpenAI planner; heuristic fallback may differ offline).

### What we learned

- Vague tool blurbs → wrong modality.  
- Multi-step must be **taught** as “both tools,” not assumed.  
- Version-tagging descriptions makes the PE log auditable.
