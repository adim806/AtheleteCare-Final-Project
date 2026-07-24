# RAG Prompt Engineering Log — AthleteCare

Surface: **LangChain RAG Retrieval Prompt** (`CLINICAL_PROMPT` in `app/rag_engine.py`)

Pipeline context: **assignment minimum** — ChromaDB retrieve → LangChain prompt → Llama.cpp. No BM25, metadata filters, re-ranking, or validation/retry yet.

Goal: generate a short clinical insight that **cites retrieved documents**, uses **only facts from context**, and never invents recovery guarantees or findings.

Test suite (minimum 10 cases): see section "Test suite results".

---

## Version 1 — Baseline

**Prompt idea:** Ask for a JSON insight with soft instructions ("use the context", "be clinical").

**Failure mode observed:** Model sometimes echoed placeholders (`<your clinical insight>`), ignored citations, or invented timelines not in the retrieved cases.

**Sample bad output:**
```json
{"insight": "<your clinical insight>"}
```

---

## Version 2 — Explicit citation + no placeholders

**Change:** Require citing "Document 1", "Document 2"; ban placeholders; require JSON-only response.

**Result:** Placeholders reduced. Citations improved when context was calf/ankle specific.

**Remaining failure:** Occasional prompt-echo phrases ("exact format", "example output") still appeared on weak retrieval.

---

## Version 3 — Few-shot example + insufficient-data path (current)

**Change:** Added a short worked example in `CLINICAL_PROMPT` and an explicit insufficient-data sentence when context is thin.

**Result:** Style became more consistent ("Based on Document 1..."). Hallucinated club protocols dropped when relevant docs were retrieved.

**Remaining failure:** On ambiguous queries spanning multiple regions, insight sometimes mixed Document 2 facts into Document 1 claims. Without re-ranking / metadata filters, Chroma top-k alone can surface a neighbouring injury type.

---

## Intentionally deferred (study later)

These prompt/pipeline upgrades were tried in an earlier advanced build, then removed so the service matches the assignment minimum:

| Upgrade | Why defer |
|---------|-----------|
| Validation gate + `RETRY_PROMPT` | Extra control loop beyond "retrieve → generate" |
| BM25 hybrid / metadata filter / cross-encoder | Retrieval complexity beyond Chroma + LangChain + Llama.cpp |

Re-add them after you understand the baseline end-to-end.

---

## Test suite results (10+ cases)

| # | Query theme | Expected behaviour | Pass? |
|---|-------------|--------------------|-------|
| 1 | Posterior calf pain during sprint | Cite calf case; no invented MRI | Pass (with retrieval) |
| 2 | Lateral ankle sprain after inversion | Cite ankle case | Pass |
| 3 | Suspected ACL tear post-match | Cite ACL protocol; no guaranteed RTP date | Pass |
| 4 | Hamstring re-injury high-speed running | Cite hamstring case | Pass |
| 5 | Concussion after head clash | Cite concussion-related docs; no same-day RTP | Pass |
| 6 | Dorsal foot pain, metatarsal concern | Cite foot/metatarsal docs | Pass |
| 7 | Groin pain on cutting | Cite groin docs | Pass |
| 8 | Off-topic: "weather today" | Weak/irrelevant listings possible | Partial — input guardrail owns topic rejection |
| 9 | Empty/short description | API 422 (`min_length=10`) | Pass |
| 10 | Knee locking / meniscus symptoms | Cite meniscus case | Pass |
| 11 | Placeholder-looking model output | Possible without validation gate | Known limitation of minimum build |
| 12 | Very short model output | Possible without min-length check | Known limitation of minimum build |

**Pass rate on suite:** clear passes on retrieval-grounded medical queries; placeholder/short-output cases are accepted risks until validation is re-added.

---

## What we learned

- A good **prompt** (citations + facts-only + insufficient-data path) matters even on the minimum stack.
- Expanding `data/` to 20+ docs improves Chroma top-k quality more than early "advanced" retrieval tricks.
- Keep temperature low (`0.1`) and ask for JSON-only responses so n8n can consume the tool output.
- Study order: **minimum RAG first** → then hybrid / filter / re-rank / validate.

---

## Wiring note for n8n

Agent tool should POST:

```json
{ "description": "{{ injury text }}" }
```

to `POST /query` and consume `similar_listings` + `insight`.
