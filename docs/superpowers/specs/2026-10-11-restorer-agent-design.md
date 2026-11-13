# Restorer as a multimodal n8n agent — design

Date: 2026-10-11 · Status: approved in chat (approach A), awaiting spec review

## Goal
Today the Restorer is a fixed pipeline: guardrail → build one request → one Gemini HTTP call → parse.
It makes no decisions, has no tools and no memory. Make it a real n8n **AI Agent** that *sees* the
plate and the photograph, *chooses* to examine other plates and look up documented features, and
*remembers* earlier findings — visible as an agent with tool sub-nodes on the n8n canvas.

## Constraints
- Free Gemini key, model `gemini-flash-latest` (Pro has no free quota on this key).
- `/webhook/turn` request and reply shape unchanged; `files/game.html` only changes for torch finds (below).
- All changes go through `tools/build_workflows.py` (+ `db/init.sql`, `tools/apply_keys.py`,
  `tools/credentials.template.json`); `setup.ps1` deploys. UI edits are overwritten.
- The Restorer never states a verdict, attribution or date (existing guardrail + output filter stay).

## Architecture (inside the single workflow `fcGame0000000001`)
```
/turn → … → Which expert? ─(restorer)→ Read plate for Restorer → Restorer payload
   → Restorer - Validate & Guardrail → Blocked?
        ├─ yes → Build Refusal ───────────────────────────────┐
        └─ no  → Restorer Agent ──→ Parse & Validate ───────────┴→ Normalize reply → …
                   ├ ai_languageModel: Gemini Chat Model (Restorer)
                   ├ ai_memory:        Restorer Memory (Postgres chat memory)
                   ├ ai_tool:          examine_plate  (Call n8n Workflow tool → same workflow)
                   └ ai_tool:          plate_notes    (Postgres tool)

Execute Workflow Trigger "examine_plate request" → Examine: read plate → Examine: to base64
   → Examine: build request → Examine: Gemini Vision (HTTP, retries) → Examine: reply text
```
`Build Gemini Request` and `Gemini Vision` (the old single call) are removed from the Restorer branch.

### Restorer Agent (`@n8n/n8n-nodes-langchain.agent` 3.1)
- Input item carries **two binary images** (`plate`, `photo`) plus `case_id`, `session_id`,
  `image_type`, `region`, `question`, `clue` (optional). Option *Automatically Passthrough Binary
  Images* = on, so the model receives both pictures with the prompt.
- System prompt = the existing Restorer rules (physical observations only; no verdict, attribution,
  dates, archive) + how to work: look at the images first; call `plate_notes` for the plate in
  question; call `examine_plate` when another plate would confirm or contradict what it sees
  (max 2 calls); never describe a feature that neither the images nor the notes support.
- Output: the existing RestorerFindings JSON (image_type, simulated, observations, anomalies_detected,
  confidence, refused, refusal_reason) via a **Structured Output Parser** sub-node, so
  `Parse & Validate` keeps its schema checks and banned-word filter (input changes from the raw
  Gemini response to the agent's `output` object).
- `maxIterations` 5; the agent node gets the same error routing as other agents (failure →
  "could not answer", no action spent).

### Gemini Chat Model (Restorer) (`lmChatGoogleGemini` 1.2)
`models/gemini-flash-latest`, temperature 0.2. New credential `fcGeminiRestoAI1`
"Gemini - Restorer" (`googlePalmApi`), key = `GEMINI_KEY_RESTORER` or fallback `GEMINI_KEY_CURATOR`
(same rule as the existing header credential).

### Tool `examine_plate` (`toolWorkflow`, calls `fcGame0000000001`)
- Inputs (from AI): `kind` ∈ {uv, xray, macro, raking_light}, `focus` (free text, e.g. "upper left",
  "the marked area"). `case_id` and `region` are injected from the current item, not chosen by AI.
- Sub-flow validates `kind`/`case_id` against whitelists, reads `/files/plates/<case>_<kind>.png`,
  sends it with the focus (and region as box_2d when present) to Gemini with a short "describe only
  what is physically visible in this area" prompt, returns plain text (≤ 120 words).
- HTTP node: retry 3× / 3 s on 429/503 (same as other free-tier calls).

### Tool `plate_notes` (`postgresTool`)
- New table `plate_notes(case_id, kind, x, y, r, feature, description)`; `x, y, r` are fractions
  (same coordinates as `CLUES` in `game.html`), `r` may be null for whole-plate notes.
- Query: `SELECT kind, feature, description, x, y, r FROM plate_notes WHERE case_id = $1 AND kind = $2`
  with `case_id` from the item and `kind` from AI.
- Rows describe physical features only (from `make_plates.py`): e.g. widow's supper X-ray "large
  oval form under the left figure; a horizon-like band turned 90°"; blue horses UV "white of the two
  tree trunks absorbs UV and reads dark; other whites fluoresce yellow-green"; starry night UV "four
  small dark sharp-edged patches"; plus one whole-plate note per plate (UV varnish glow, macro
  crack pattern, raking-light relief). No verdicts, no dates, no material names.
- Seeded in `db/init.sql`; the running database gets the same rows once via `psql` (idempotent:
  `CREATE TABLE IF NOT EXISTS` + insert only when empty).

### Restorer Memory (`memoryPostgresChat`)
Session key `<session_id>:<case_id>:restorer`, context window 6 messages, Postgres credential.
The node creates its own table (`restorer_chat_histories`).

### Torch finds (`files/game.html`)
The automatic torch question also sends the clue label in the message text
("…The feature: <label>. What is it, and what does it tell us?") so the agent anchors on
`plate_notes`. No server-side change for this.

## Error handling
- Guardrail refusals never reach the model (unchanged).
- Agent/tool failures → existing `Agent failed` → `Normalize reply` → "could not answer", no action spent.
- Unparseable agent output → `Parse & Validate` fail branch (unchanged behaviour).
- `examine_plate` with a bad `kind` returns an error string to the agent, not an exception.

## Risks (checked first, before the full build)
1. Gemini chat model in n8n 2.41 accepts passed-through binary images. Fallback: send images inside
   `examine_plate` only (the agent then "sees" through its tool).
2. A `toolWorkflow` tool can call a sub-flow inside its own workflow. Fallback: approach B
   (internal webhook + HTTP Request tool, whitelisted inputs).
3. Free-tier rate limit with 2–4 calls per turn. Mitigation: max 2 tool calls in the prompt, retries.

## Testing
- `build_workflows.py` self-check (`check()`) passes; new asserts on every patch.
- Live `/webhook/turn` calls: plain question per case; torch-find question; off-topic question
  (refused without model call); follow-up question that relies on memory.
- Inspect the n8n execution data for one turn: agent called `plate_notes` and/or `examine_plate`.
- Game page still renders replies; `/verdict` unaffected.

## Out of scope
Zoom/crop tool; changing the Scientist/Curator/Archivist; a paid model; scoring changes.
