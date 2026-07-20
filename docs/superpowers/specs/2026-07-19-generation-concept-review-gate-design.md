# Generation Concept-Review Gate — Design

- **Date:** 2026-07-19
- **Branch:** branch3
- **Status:** approved (pre-implementation)

## Problem / Goal

Today the Generation flow renders a graphic in one shot from an auto-generated
brief — the user never sees the *idea* before a render is spent on it. Add a
**concept-review checkpoint**: the strategist proposes an idea, the user reviews
the overall theme (and optionally tweaks or regenerates it), confirms, and only
then is the graphic rendered.

The emphasis is the **theme making sense**, not precise copy editing. Fine-grained
copy fixes are deferred to a future post-generation editor and are out of scope
here.

## Approach — split the pipeline (chosen over two alternatives)

`run()` currently does brief -> graphic in one pass. Split it at the brief so the
**brief becomes the single hand-off object** between planning and rendering.
Rejected: (2) a `brief=` parameter on `run()` (muddies its contract); (3)
orchestrating in the Streamlit page (duplicates `run()`'s file/draft handling,
drifts over time).

## Components

- **`generate_brief(topic, brain, brand, product_name=None, steer=None)`** —
  *existing planner*; add an optional `steer` string appended as one extra line
  in the strategist prompt. No steer -> today's behavior exactly. Used for both
  the initial proposal and "Try a different idea".

- **`render_from_brief(brief, brand, logo_path, *, product_name=None,
  caption_path=None, html_path=None, brief_path=None, png_path=None) -> dict`** —
  *new*; the rendering half extracted verbatim from `run()`: path defaults +
  stale-draft clearing, `brand_to_prompt`, `brief_to_caption`,
  `brief_to_post_content`, save brief+caption, `_choose_design_skill`,
  `generate_graphic`, save html, return the same dict `run()` returns today.

- **`run(...)`** — unchanged signature and behavior; body becomes:
  load brand/brain/logo -> `generate_brief(...)` -> `render_from_brief(...)`.
  CLI and existing callers unaffected.

- **`fit_brief_copy(brief) -> (brief, changes)`** — *new, in `strategy_agent.py`*;
  the "minor repolish". Runs `validate_brief` to find over-limit fields; ONLY
  those get a light constrained LLM trim that preserves wording; within-limit
  fields are returned byte-for-byte. Returns the adjusted brief + a small list of
  what changed. On any LLM failure it returns the brief unchanged (graceful — the
  defect gate still catches visual overflow downstream).

## UX & data flow (`pages/2_Generation.py`)

**State:** `st.session_state.proposal` (the working brief) + a signature of
`(brand, topic, product)` for staleness detection.

**Flow:**
1. **Inputs (as today):** brand selector + topic (+ optional product).
2. **(1) "Propose idea"** -> runs `generate_brief` in a spinner -> stores the brief
   as `proposal` -> the review panel appears. No graphic yet.
3. **Review panel** (whenever a proposal exists):
   - **Concept summary (top, primary):** plain-English framing of the idea —
     post type, hero message / angle, caption preview, proof metrics, CTA. The
     "does this make sense?" confirmation surface.
   - **"Tweak the idea" expander (secondary):** editable fields (caption
     hook/body/cta, graphic headline/hero/contrast/subtext/metrics/cta, and the
     **optional layout note**) + an **"Apply tweaks"** button. Clicking Apply:
     (a) auto-saves the edits into the proposal (nothing lost), (b) runs
     `fit_brief_copy` and shows any trims, (c) re-renders the concept summary with
     the polished brief so the user confirms the fitted version. Stays in review.
   - **"Try a different idea":** optional one-line steer box + button ->
     `generate_brief(steer=…)` -> replaces the proposal (fresh idea; discards
     unsaved tweaks).
   - **"Generate graphic" (separate, primary button):** renders the current
     confirmed proposal via `render_from_brief` -> displays caption + graphic +
     the existing before/after draft view.
4. **Unsaved-tweaks hint:** if field values differ from the saved proposal, show
   a subtle "unsaved tweaks — Apply first" note.
5. **Staleness guard:** changing brand/topic after proposing flags "inputs changed
   — propose again" instead of rendering a stale idea.

Net: the page's old single "Generate" becomes **Propose -> [optionally Apply
tweaks -> confirm polished brief]* -> Generate**. Apply and Generate are separate
deliberate actions; the fit-polish happens at Apply time so the user always
confirms fitted copy.

## Error handling (graceful degradation — never crash the UI)

- **Strategist fails** (`generate_brief` empty) -> "couldn't draft an idea — try
  again"; stay on inputs; no crash.
- **Fit-polish fails** -> return brief unchanged + note "couldn't auto-fit, using
  your copy as-is"; defect gate still catches visual overflow.
- **Regenerate fails** -> keep the previous proposal, show a warning.
- **Render** -> existing `generate_graphic` safety (validation retry + defect
  gate, never raises); warnings surface as today.
- **Blanked required field** on Apply -> flagged; Generate blocked until filled.
- **Staleness** -> handled as above.

## Testing (live acceptance per CLAUDE.md — mocks have missed real-model behavior)

- **Primary live acceptance: 2 automatic runs each for Finbots, Stripe, Hims (6
  total)** through the new render path. Covers both design lanes (Finbots + Stripe
  -> marketing-graphic skill; Hims -> canvas skill) with two samples apiece for
  run-to-run variance. Each must render without unhandled error, with exact copy
  present and no crash. These runs also prove the split (they exercise both
  `generate_brief` and `render_from_brief`).
- **`render_from_brief`** with a hand-built brief renders a graphic (the split's
  second half in isolation).
- **`generate_brief(steer=…)`** — a steer (e.g. "lean on cost savings") visibly
  shifts the proposal.
- **`fit_brief_copy`** — an over-limit headline is trimmed while an in-limit field
  is left byte-for-byte; the LLM-failure path returns the brief unchanged.
- **`run()` smoke check** — one call confirms the three-line wrapper still
  composes. Largely redundant with the 6 brand runs (which already exercise both
  halves); kept only as a cheap sanity check, not a full regression suite.
- **Manual Streamlit walkthrough:** propose -> tweak -> apply (see polished brief +
  trim notes) -> confirm -> generate; propose -> regenerate-with-steer -> generate;
  the staleness flag.

## Out of scope

- Precise post-generation copy editing (a separate future feature).
- Design skill / style selection at the gate — routing stays automatic; the
  optional layout note provides light direction steering.
