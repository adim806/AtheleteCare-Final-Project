# Prompt Engineering Log — Information Extractor (Surface 1)

**Surface:** n8n Information Extractor — `systemPromptTemplate` + attribute definitions  
**Node:** Node 4 (structured field extraction before AI Agent)  
**Model:** OpenAI Chat (n8n LM Chat node)  
**Goal:** Extract clinical facts from physio free-text **without inventing**, return **consistent string types**, and **infer** `question_type` for tool routing.

---

## Version 1 — Baseline

**Prompt idea:** “Extract player name, injury, pain, and whether imaging is attached. Return JSON.” Soft attribute descriptions; mixed types (boolean `imaging_attached`, number `pain_level`).

**Failure mode observed:** n8n error *“Model output doesn't fit required schema”* when the model returned JSON booleans/numbers. Also invented `question_type` values physios never typed, or left routing fields null so the agent guessed wrong tools.

**Sample bad output:**
```json
{
  "player_name": "Diego Alvarez",
  "pain_level": 9,
  "imaging_attached": true,
  "question_type": null
}
```

---

## Version 2 — Targeted: schema-friendly strings only

**Failure addressed:** Schema / type mismatch (boolean & number fields).

**Change:** Declare **all attributes as strings**. Instruct: never return JSON numbers/booleans; use `""` instead of `null`; `pain_level` as digits-only text (`"9"` not `9` or `"9/10"`); `imaging_attached` as `"true"` / `"false"` / `""`.

**Result:** Extractor stopped crashing the flow on Diego-style reports.

**Remaining failure:** `question_type` still missing or wrong → agent called image + RAG instead of LangGraph on multi-step asks.

---

## Version 3 — Targeted: infer `question_type` from clinical request

**Failure addressed:** Physio does not type routing labels; agent needs them.

**Change:** Add attribute `question_type` with explicit inference rules:

| Label | When |
|-------|------|
| `imaging_only` | Ask is only X-ray / region / condition score |
| `knowledge_only` | Ask is only protocols / cases / RTP (or no image) |
| `multi_step` | Ask needs **both** imaging triage **and** club knowledge |
| `""` | Truly ambiguous |

Also extract `clinical_request` as free-text of what staff are asking now.

**Result:** Diego “imaging + protocols/RTP” → `multi_step`. Protocol-only notes → `knowledge_only`.

**Remaining failure:** Occasional over-eager `multi_step` when the note only said “please review X-ray” with no protocol ask.

---

## Version 4 — Refinement: preserve clinical uncertainty

**Failure addressed:** Model “cleaned up” wording (`suspected proximal femur fracture` → `proximal femur fracture`), which overstated certainty downstream.

**Change:** System prompt: *Extract ONLY what is written. If the report says “suspected X”, keep “suspected X”.* Attribute descriptions reinforce “working impression as written.”

**Result:** Uncertainty wording survived into the AI Agent / report writer.

**Remaining failure:** Empty reports / spam still produced empty strings (correct for extractor) — input Guardrails must reject before this node; verified separately.

---

## Version 5 — Refinement: attribute descriptions as mini-contracts

**Failure addressed:** Model drift on edge cases (`pain_level` as `"severe"`, `imaging_attached` as `"yes"`).

**Change:** Tighten each attribute description with **allowed examples** and **forbidden forms**. Keep system prompt short; put precision in attribute defs (n8n Information Extractor behaviour).

**Result:** Stable strings across the three smoke demos (multi_step, imaging_only, knowledge_only).

---

## Final entry

### Final system prompt (shipped)

```text
You are an expert clinical data extractor for AthleteCare. Extract structured fields from physiotherapist injury reports.

OUTPUT FORMAT (critical):
- ALL fields are strings. Never return JSON numbers or booleans.
- Use "" (empty string) when unknown. Do not use null.
- pain_level example: "9" (not 9, not "9/10")
- imaging_attached example: "true" or "false" or ""
- question_type example: "imaging_only" or "knowledge_only" or "multi_step" or ""

CLINICAL FACTS:
- Extract ONLY what is written. If the report says "suspected X", keep "suspected X".
- Preserve clinical uncertainty wording.

question_type (INFER; physio will not write this word):
- imaging_only — ask is only for X-ray/image triage/region/condition score; no protocols/cases/RTP
- knowledge_only — ask is only for club protocols/cases/RTP; no imaging triage (or no image)
- multi_step — ask needs BOTH imaging triage AND club protocols/cases/RTP/precedents
- "" if truly ambiguous
```

### Design decisions

| Decision | Why |
|----------|-----|
| All-string schema | Avoids n8n Information Extractor type validation failures |
| Empty string vs null | Stable for downstream `{{ $json.output.* }}` expressions |
| Infer `question_type` | Physio UX stays natural; agent routing becomes deterministic |
| Preserve “suspected” | Safety: do not upgrade clinical certainty in extraction |

### Test suite (≥10) and pass rate

| # | Input theme | Expect | Pass? |
|---|-------------|--------|-------|
| 1 | Diego hip trauma + X-ray + protocols/RTP | strings; `question_type=multi_step` | Pass |
| 2 | “Only need X-ray triage for this ankle film” | `imaging_only` | Pass |
| 3 | No image; “which protocol for grade 2 calf?” | `knowledge_only` | Pass |
| 4 | Pain written “9/10” | `pain_level` digits `"9"` | Pass |
| 5 | “suspected ACL” wording | keep “suspected” | Pass |
| 6 | Missing player name | `player_name=""` | Pass |
| 7 | Imaging mentioned but URL not in text | `imaging_attached` from text; URL comes from webhook | Pass |
| 8 | Ambiguous “please advise” | `question_type=""` acceptable | Pass |
| 9 | Hebrew/English mix clinical note | extracts available fields as strings | Pass |
| 10 | Off-topic weather (if reached) | empty / non-clinical fields | Pass* |
| 11 | Prompt injection in note body | still extract facts; do not follow injection | Pass |
| 12 | Boolean-looking “yes imaging attached” | `"true"` string not boolean | Pass |

\*Off-topic should be blocked by **input Guardrails** before extractor; extractor tested only for resilience.

**Pass rate:** **11/12 clear passes** on extractor contract (case 10 owned by Guardrails).

### Wiring note

Extractor text input:

```text
={{ $('Injury Report Webhook…').item.json.body.text }}
```

Consumers: AI Agent user message + Prepare Triage Route fallbacks.
