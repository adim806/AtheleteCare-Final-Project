# Prompt Engineering Log — RAG Retrieval (Surface 3)

**Surface:** LangChain RAG retrieval / generation prompt  
**Component:** Service 1 — `RAG-Service/app/main.py` → `prompt_template`  
**Stack:** ChromaDB retrieve → LangChain `PromptTemplate` → Llama.cpp (GGUF)  
**Pipeline context:** Assignment **minimum** — no BM25, metadata filters, re-ranking, or validation/retry.  
**Goal:** Short clinical insight that **cites retrieved document IDs**, uses **only context facts**, and says **Insufficient data** when context does not match.

---

## Version 1 — Baseline

**Prompt idea:** Ask for a JSON insight with soft instructions (“use the context”, “be clinical”).

**Failure mode observed:** Model echoed placeholders (`<your clinical insight>`), ignored citations, or invented recovery timelines not in retrieved cases.

**Sample bad output:**
```json
{"insight": "<your clinical insight>"}
```

---

## Version 2 — Targeted: explicit citation + no placeholders

**Failure addressed:** Placeholders and missing citations.

**Change:** Require citing retrieved docs; ban placeholders; prefer structured/short answers.

**Result:** Placeholders reduced. Citations improved on calf/ankle queries.

**Remaining failure:** Prompt-echo phrases (“exact format”, “example output”) on weak retrieval.

---

## Version 3 — Targeted: ID citation + insufficient-data path

**Failure addressed:** Hallucinated protocols when top-k was weak; vague “Document N” citations hard to audit.

**Change:** Role = club clinical memory. Require starting with exact ID citation (e.g. `[Based on ID: CASE-2024]`). If context does not match, say **Insufficient data**. Cap length (max ~3 sentences).

**Result:** Actionable, citable insights when Chroma retrieved the right cases.

**Remaining failure:** Ambiguous multi-region queries sometimes blended neighbouring injury types from top-k (retrieval limit of minimum stack).

---

## Version 4 — Refinement: tighten “ONLY on the context” wording

**Failure addressed:** Occasional advice not present in chunks (generic web-knowledge style).

**Change:** Emphasise “based ONLY on the context below” and “Do NOT hallucinate medical advice” as strict guidelines numbered in the prompt.

**Result:** Fewer unsupported RTP claims on in-domain queries.

**Remaining failure:** Very short model outputs still possible without a validation gate (accepted for minimum build).

---

## Version 5 — Refinement: keep prompt short for Llama.cpp

**Failure addressed:** Long few-shot prompts degraded small GGUF adherence.

**Change:** Final shipped prompt stays compact (role + context + request + 3 rules + “Clinical Insight:”). Prefer expanding `data/` corpus (≥20 docs) over stuffing examples into the prompt.

**Result:** More stable local generations; n8n tool responses remained consumable.

---

## Final entry

### Final prompt (shipped)

```text
You are the Head Clinical Knowledge AI for a professional football club ("The Club's Memory").
Write a SHORT, direct clinical insight (max 3 sentences) based ONLY on the context below.

Retrieved Clinical Knowledge:
{context}

Clinical Request / Injury Description:
"{description}"

Strict Guidelines:
1. You MUST start your answer by citing the exact ID (e.g., "[Based on ID: CASE-2024]").
2. Do NOT hallucinate medical advice. If the context doesn't match the injury, say "Insufficient data".
3. Keep the output concise and directly actionable for the medical team.

Clinical Insight:
```

Location: `RAG-Service/app/main.py` (`prompt_template`).

### Design decisions

| Decision | Why |
|----------|-----|
| Exact CASE/PROT ID citation | Auditable for clinicians and graders |
| Insufficient-data escape | Better than confident hallucination |
| Short prompt for GGUF | Local models follow brevity better |
| Minimum retrieval stack | Matches assignment before advanced IR |

### Intentionally deferred

| Upgrade | Why defer |
|---------|-----------|
| Validation gate + retry prompt | Beyond retrieve → generate |
| BM25 hybrid / metadata filter / re-rank | Beyond Chroma + LangChain + Llama.cpp |

### Test suite (≥10) and pass rate

| # | Query theme | Expected behaviour | Pass? |
|---|-------------|--------------------|-------|
| 1 | Posterior calf pain during sprint | Cite calf case; no invented MRI | Pass |
| 2 | Lateral ankle sprain after inversion | Cite ankle case | Pass |
| 3 | Suspected ACL tear post-match | Cite ACL-related docs; no guaranteed RTP date | Pass |
| 4 | Hamstring re-injury high-speed running | Cite hamstring case | Pass |
| 5 | Concussion after head clash | Cite concussion docs; no same-day RTP | Pass |
| 6 | Dorsal foot pain, metatarsal concern | Cite foot/metatarsal docs | Pass |
| 7 | Groin pain on cutting | Cite groin docs | Pass |
| 8 | Off-topic: “weather today” | Weak insight possible | Partial — input Guardrails owns rejection |
| 9 | Empty/too-short description | API validation (`min_length`) | Pass |
| 10 | Knee locking / meniscus symptoms | Cite meniscus case | Pass |
| 11 | Placeholder-looking output | Possible without validation gate | Known limitation |
| 12 | Mismatched context (wrong body region in top-k) | Prefer Insufficient data | Partial |

**Pass rate:** Strong on retrieval-grounded medical queries (**~9/12** clear); cases 8/11/12 are accepted limitations of the minimum stack or owned by Guardrails.

### What we learned

- Citation + facts-only + insufficient-data beats soft “be helpful” prompts on Llama.cpp.  
- Corpus coverage (≥20 docs) often helps more than early re-ranking.  
- Keep temperature low for tool stability in n8n.

### Wiring note for n8n

```json
{ "description": "<short clinical facts>" }
```

`POST /query` → consume `similar_listings` + `insight`.
