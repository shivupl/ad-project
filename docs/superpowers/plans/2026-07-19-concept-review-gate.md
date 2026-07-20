# Concept-Review Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Insert a human review/edit checkpoint between the strategist and the graphic renderer so the user confirms (or steers) the proposed idea before a graphic is generated.

**Architecture:** Split the one-shot `run()` at the brief. `generate_brief` (planning, now with an optional `steer`) and a new `render_from_brief` (rendering) become independent halves; `run()` is a thin wrapper that chains them for the CLI. A new `fit_brief_copy` does a light conform-to-fit pass on edited copy. The Streamlit Generation page becomes a two-step flow (propose → review/tweak/regenerate → confirm → generate) driving the two halves directly.

**Tech Stack:** Python 3.9, Streamlit, Anthropic SDK (via `llm.py`), Playwright (rendering), PIL (test logo).

## Global Constraints

- Interpreter `./venv/bin/python3` — **Python 3.9**: `list[str]` ok, `X | Y` unions are NOT (they crash).
- Model IDs live ONLY in `llm.py`; call models via `llm.complete` / `llm.complete_json`.
- **Graceful degradation:** nothing in the pipeline raises through to destroy state; a failed LLM enhancement returns the previous good value and prints.
- **Copy discipline (unchanged):** `MAX_GRAPHIC_METRICS = 2`; word limits `GRAPHIC_WORD_LIMITS = {"headline": 8, "contrast_line": 8, "subtext": 12, "cta": 5}`; `METRIC_WORD_LIMIT = 6` (all in `strategy_agent.py`).
- **Testing convention:** the repo has no pytest suite and CLAUDE.md distrusts mocks for model *behavior*. So: logic-only units are verified by deterministic scripts that monkeypatch `llm.complete_json` / the `brain_to_context` import (plumbing, not behavior); generation is verified by `py_compile` + **live API runs**. Deterministic test scripts live in `tests/` and run as `./venv/bin/python3 tests/<name>.py` (exit 0 = pass).
- Branch: **branch3**. Restart Streamlit after code changes.
- `data/` is gitignored (brand/brain JSONs, `logo_<slug>.png`, outputs).

---

### Task 1: Split `run()` — extract `render_from_brief`, make `run()` a thin wrapper

**Files:**
- Modify: `layer2_generation/graphic_generator.py` (the `run()` function near the bottom)

**Interfaces:**
- Produces: `render_from_brief(brief: dict, brand: dict, logo_path: str, *, product_name=None, caption_path=None, html_path=None, brief_path=None, png_path=None) -> dict` — returns the exact dict `run()` returns today (keys: brief, caption, post_content, html, warnings, critique, design_skill, caption_path, html_path, brief_path, png_path, draft_html_path, draft_png_path).
- Produces: `run(...)` unchanged external contract.
- Consumes: existing `generate_brief`, `brief_to_caption`, `brief_to_post_content`, `_choose_design_skill`, `generate_graphic`, `validate_brief`, `load_logo_b64`, `brand_to_prompt`.

- [ ] **Step 1: Replace the `run()` definition** with `render_from_brief` + a slim `run()`.

Replace the entire current `def run(...)` (from `def run(` through its `return { ... }`) with:

```python
def render_from_brief(brief: dict, brand: dict, logo_path: str, *,
                      product_name: str = None, caption_path: str = None,
                      html_path: str = None, brief_path: str = None,
                      png_path: str = None) -> dict:
    """Render a (possibly user-edited) brief into caption + HTML graphic + PNG.
    The second half of the pipeline, split from run() so a human review step
    can sit between planning (generate_brief) and rendering."""
    caption_path = caption_path or str(DATA_DIR / "caption.txt")
    html_path = html_path or str(DATA_DIR / "output.html")
    brief_path = brief_path or str(DATA_DIR / "brief.json")
    png_path = png_path or str(DATA_DIR / "output.png")
    draft_html_path = str(Path(html_path).with_name(Path(html_path).stem + "_draft.html"))
    draft_png_path = str(Path(png_path).with_name(Path(png_path).stem + "_draft.png"))
    for stale in (draft_html_path, draft_png_path):
        Path(stale).unlink(missing_ok=True)

    logo_b64 = load_logo_b64(logo_path)
    brand_prompt = brand_to_prompt(brand)

    caption = brief_to_caption(brief)
    post_content = brief_to_post_content(brief, LOGO_PLACEHOLDER)

    with open(brief_path, "w") as f:
        json.dump(brief, f, indent=2)
    with open(caption_path, "w") as f:
        f.write(caption)

    skill_path = _choose_design_skill(brand)
    print(f"Design skill: {skill_path.name}")

    html, warnings, critique = generate_graphic(brand_prompt, post_content, logo_b64, brief,
                                                png_path=png_path, skill_path=skill_path,
                                                draft_html_path=draft_html_path,
                                                draft_png_path=draft_png_path)
    warnings = validate_brief(brief) + warnings
    with open(html_path, "w") as f:
        f.write(html)

    return {
        "brief": brief,
        "caption": caption,
        "post_content": post_content,
        "html": html,
        "warnings": warnings,
        "critique": critique,
        "design_skill": skill_path.name,
        "caption_path": caption_path,
        "html_path": html_path,
        "brief_path": brief_path,
        "png_path": png_path if os.path.exists(png_path) else None,
        "draft_html_path": draft_html_path if os.path.exists(draft_html_path) else None,
        "draft_png_path": draft_png_path if os.path.exists(draft_png_path) else None,
    }


def run(topic: str, brand_path: str, brain_path: str, logo_path: str,
        product_name: str = None, caption_path: str = None, html_path: str = None,
        brief_path: str = None, png_path: str = None) -> dict:
    """Full non-interactive pipeline: topic -> brief -> caption + graphic + PNG.
    A thin wrapper: plan the brief, then render it. The interactive two-step
    flow (human review between) lives in the Streamlit page and calls
    generate_brief / render_from_brief directly."""
    with open(brand_path) as f:
        brand = json.load(f)
    with open(brain_path) as f:
        brain = json.load(f)

    brief = generate_brief(topic, brain, brand=brand, product_name=product_name)
    if not brief:
        raise RuntimeError("Strategy agent failed — no brief generated")

    return render_from_brief(brief, brand, logo_path, product_name=product_name,
                             caption_path=caption_path, html_path=html_path,
                             brief_path=brief_path, png_path=png_path)
```

- [ ] **Step 2: Compile-check**

Run: `./venv/bin/python3 -m py_compile layer2_generation/graphic_generator.py`
Expected: no output (success).

- [ ] **Step 3: Live smoke — `run()` still renders (regression)**

Run:
```bash
./venv/bin/python3 -c "
import sys; sys.path.insert(0,'.')
from layer2_generation.graphic_generator import run
r = run('Deploying a live credit scorecard in one day with CreditX',
        'data/brand_finbotsai.json', 'data/brain_finbotsai_(finbotsai_pte_ltd).json',
        'data/logo_hims.png', png_path='data/_smoke.png')
print('png:', r.get('png_path'), 'skill:', r.get('design_skill'))
assert r.get('png_path'), 'no PNG produced'
print('RUN SMOKE OK')
"
```
Expected: prints `RUN SMOKE OK` with a non-None png path. (Uses the Hims logo as a stand-in since Finbots has no logo asset; we only care that the pipeline completes.)

- [ ] **Step 4: Commit**

```bash
git add layer2_generation/graphic_generator.py
git commit -m "refactor: split run() into generate_brief + render_from_brief"
```

---

### Task 2: Add `steer` to `generate_brief`

**Files:**
- Modify: `layer2_generation/strategy_agent.py` (`generate_brief`)
- Test: `tests/test_steer.py`

**Interfaces:**
- Produces: `generate_brief(topic, brain, brand=None, product_name=None, steer=None) -> dict` — when `steer` is a non-empty string, it is injected into the strategist prompt; when None/empty, behavior is identical to today.

- [ ] **Step 1: Write the failing test** — `tests/test_steer.py`

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import llm
import layer2_generation.strategy_agent as sa

captured = {}

def fake_json(content, **kw):
    captured["content"] = content
    return {"caption": {}, "graphic": {}}

# stub out the LLM + the context builders so we can inspect the assembled prompt
llm.complete_json = fake_json
sa.brain_to_context = lambda brain, product_name=None, topic=None: "BRAIN"
sa.marketing_profile_to_context = lambda brand: "PROFILE"

sa.generate_brief("Topic X", {"key_metrics": []}, steer="lean on cost savings")
assert "lean on cost savings" in captured["content"], "steer text missing from prompt"

sa.generate_brief("Topic X", {"key_metrics": []})
assert "lean on cost savings" not in captured["content"], "stale steer leaked"
assert "ADDITIONAL DIRECTION" not in captured["content"], "steer block present without steer"

print("OK: steer reaches the prompt only when provided")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `./venv/bin/python3 tests/test_steer.py`
Expected: `TypeError: generate_brief() got an unexpected keyword argument 'steer'`.

- [ ] **Step 3: Implement — add the `steer` parameter and prompt block**

In `generate_brief`, change the signature and insert a steer block. Replace the signature line and the `user_message` assignment:

```python
def generate_brief(topic: str, brain: dict, brand: dict = None,
                   product_name: str = None, steer: str = None) -> dict:
    """Topic + brain JSON (+ optional brand JSON for its marketing profile) →
    structured post brief. `steer` (optional) nudges the idea in a direction."""

    brain_context = brain_to_context(brain, product_name=product_name, topic=topic)
    profile_block = (marketing_profile_to_context(brand) if brand else "") or DEFAULT_PROFILE_LINE
    steer_block = f"\nADDITIONAL DIRECTION FROM THE USER (steer the idea accordingly):\n{steer}\n" if steer else ""

    user_message = f"""
COMPANY KNOWLEDGE:
{brain_context}

{profile_block}

USER TOPIC:
{topic}
{steer_block}
Generate the best possible LinkedIn post brief for this topic using only facts from the company knowledge above.
Adapt post type, register, and copy density to the MARKETING PROFILE.
Remember: caption and graphic are separate artifacts with separate word budgets.
"""

    return llm.complete_json(user_message, max_tokens=1500, system=STRATEGY_SYSTEM_PROMPT) or {}
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `./venv/bin/python3 tests/test_steer.py`
Expected: `OK: steer reaches the prompt only when provided`.

- [ ] **Step 5: Commit**

```bash
git add layer2_generation/strategy_agent.py tests/test_steer.py
git commit -m "feat: add optional steer to generate_brief"
```

---

### Task 3: Add `fit_brief_copy` (conform-to-fit pass)

**Files:**
- Modify: `layer2_generation/strategy_agent.py` (new function after `validate_brief`)
- Test: `tests/test_fit.py`

**Interfaces:**
- Produces: `fit_brief_copy(brief: dict) -> tuple[dict, list]` — returns `(possibly_adjusted_brief, changes)`. Only fields exceeding limits are touched; metric COUNT is capped deterministically; over-limit text fields are trimmed by one constrained `llm.complete_json` call preserving wording. Never raises — on LLM failure the text is left unchanged. `changes` is a list of human-readable strings.

- [ ] **Step 1: Write the failing test** — `tests/test_fit.py`

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import llm
import layer2_generation.strategy_agent as sa

# 1) within-limits brief: untouched, no LLM call (llm raises to prove it isn't called)
llm.complete_json = lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM should not be called"))
brief = {"graphic": {"headline": "Deploy in 1 day", "cta": "Book a demo",
                     "metrics": ["-92% deploy time", "+96 pts GINI"]}}
out, changes = sa.fit_brief_copy(brief)
assert changes == [], f"expected no changes, got {changes}"
assert out["graphic"]["headline"] == "Deploy in 1 day"

# 2) metric count > 2: deterministic truncation, still no LLM
brief2 = {"graphic": {"headline": "Deploy in 1 day", "cta": "Book a demo",
                      "metrics": ["a", "b", "c", "d"]}}
out2, changes2 = sa.fit_brief_copy(brief2)
assert out2["graphic"]["metrics"] == ["a", "b"], out2["graphic"]["metrics"]
assert any("metrics" in c for c in changes2)

# 3) over-limit headline: LLM trims it; other fields untouched
llm.complete_json = lambda *a, **k: {"headline": "Deploy a live scorecard in 1 day"}
long = "Deploy a fully live production credit scorecard in just one single day flat"
brief3 = {"graphic": {"headline": long, "cta": "Book a demo", "metrics": []}}
out3, changes3 = sa.fit_brief_copy(brief3)
assert out3["graphic"]["headline"] == "Deploy a live scorecard in 1 day"
assert out3["graphic"]["cta"] == "Book a demo"
assert any("headline" in c for c in changes3)

# 4) over-limit + LLM failure: headline left unchanged (graceful)
llm.complete_json = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
out4, changes4 = sa.fit_brief_copy({"graphic": {"headline": long, "cta": "x", "metrics": []}})
assert out4["graphic"]["headline"] == long, "should keep original on failure"

print("OK: fit_brief_copy conforms to fit and degrades gracefully")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `./venv/bin/python3 tests/test_fit.py`
Expected: `AttributeError: module 'layer2_generation.strategy_agent' has no attribute 'fit_brief_copy'`.

- [ ] **Step 3: Implement `fit_brief_copy`** (add directly after `validate_brief`)

```python
def fit_brief_copy(brief: dict) -> tuple:
    """Light 'conform to fit' pass for user-edited copy. Caps metric COUNT
    deterministically; trims only over-limit text fields via one constrained
    LLM call that preserves wording. Returns (brief, changes). Never raises —
    on LLM failure the over-limit text is left unchanged (the defect gate still
    catches visual overflow later)."""
    graphic = dict(brief.get("graphic") or {})
    changes = []

    metrics = list(graphic.get("metrics") or [])
    if len(metrics) > MAX_GRAPHIC_METRICS:
        changes.append(f"metrics: kept first {MAX_GRAPHIC_METRICS} of {len(metrics)}")
        graphic["metrics"] = metrics[:MAX_GRAPHIC_METRICS]

    over = {}
    for field, limit in GRAPHIC_WORD_LIMITS.items():
        val = (graphic.get(field) or "").strip()
        if val and len(val.split()) > limit:
            over[field] = limit

    if over:
        payload = {f: {"text": graphic.get(f, ""), "max_words": lim} for f, lim in over.items()}
        prompt = (
            "Shorten each field's text to at most max_words words WITHOUT changing "
            "its meaning, angle, or key numbers — trim filler only and keep the "
            "user's wording as much as possible. Return ONLY a JSON object mapping "
            "each field name to its shortened string.\n\n" + json.dumps(payload, indent=2)
        )
        try:
            trimmed = llm.complete_json(prompt, max_tokens=400) or {}
        except Exception as e:
            print(f"fit_brief_copy: trim failed, keeping copy as-is ({e})")
            trimmed = {}
        for f in over:
            new = (trimmed.get(f) or "").strip()
            if new and new != graphic.get(f):
                changes.append(f'{f}: "{graphic[f]}" → "{new}"')
                graphic[f] = new

    if not changes:
        return brief, []
    out = dict(brief)
    out["graphic"] = graphic
    return out, changes
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `./venv/bin/python3 tests/test_fit.py`
Expected: `OK: fit_brief_copy conforms to fit and degrades gracefully`.

- [ ] **Step 5: Commit**

```bash
git add layer2_generation/strategy_agent.py tests/test_fit.py
git commit -m "feat: add fit_brief_copy conform-to-fit pass"
```

---

### Task 4: `brief_to_summary` helper + two-step Streamlit page

**Files:**
- Modify: `layer2_generation/strategy_agent.py` (add `brief_to_summary`)
- Modify: `pages/2_Generation.py` (full rewrite to two-step flow)
- Test: `tests/test_summary.py`

**Interfaces:**
- Produces: `brief_to_summary(brief: dict) -> str` — a readable, theme-first markdown summary.
- Consumes: `generate_brief` (Task 2), `fit_brief_copy` (Task 3), `render_from_brief` (Task 1).

- [ ] **Step 1: Write the failing test** — `tests/test_summary.py`

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layer2_generation.strategy_agent import brief_to_summary

brief = {"post_type": "stat_callout",
         "graphic": {"headline": "Deploy in 1 day", "stat_hero": "1 Day",
                     "contrast_line": "vs 9-12 months", "subtext": "No code.",
                     "metrics": ["-92% deploy", "+96 GINI"], "cta": "Book a demo"},
         "caption": {"hook": "Scorecards used to take months."}}
s = brief_to_summary(brief)
for token in ["Stat Callout", "Deploy in 1 day", "1 Day", "vs 9-12 months",
              "-92% deploy", "Book a demo", "Scorecards used to take months"]:
    assert token in s, f"missing {token!r} in summary"
print("OK: brief_to_summary renders the key fields")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `./venv/bin/python3 tests/test_summary.py`
Expected: `ImportError: cannot import name 'brief_to_summary'`.

- [ ] **Step 3: Implement `brief_to_summary`** (add after `brief_to_caption` in `strategy_agent.py`)

```python
def brief_to_summary(brief: dict) -> str:
    """Readable, theme-first framing of a brief for the review gate (markdown)."""
    g = brief.get("graphic") or {}
    c = brief.get("caption") or {}
    post_type = (brief.get("post_type") or "").replace("_", " ").title() or "—"
    metrics = g.get("metrics") or []
    lines = [
        f"**Post type:** {post_type}",
        f"**Hero message:** {g.get('headline') or '—'}"
        + (f"  ·  _{g.get('stat_hero')}_" if g.get("stat_hero") else ""),
    ]
    if g.get("contrast_line"):
        lines.append(f"**Contrast:** {g['contrast_line']}")
    if g.get("subtext"):
        lines.append(f"**Supporting:** {g['subtext']}")
    if metrics:
        lines.append("**Proof:** " + " · ".join(str(m) for m in metrics[:MAX_GRAPHIC_METRICS]))
    lines.append(f"**CTA:** {g.get('cta') or '—'}")
    if c.get("hook"):
        lines.append(f"**Caption hook:** {c['hook']}")
    return "\n\n".join(lines)
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `./venv/bin/python3 tests/test_summary.py`
Expected: `OK: brief_to_summary renders the key fields`.

- [ ] **Step 5: Rewrite `pages/2_Generation.py`** with the full two-step flow

```python
import json
from pathlib import Path

import streamlit as st

from layer2_generation.graphic_generator import render_from_brief
from layer2_generation.strategy_agent import generate_brief, fit_brief_copy, brief_to_summary
from paths import DATA_DIR, ROOT

st.set_page_config(page_title="Generation", layout="wide")
st.title("Layer 2 — Generation")
st.caption("topic + brand/brain → propose idea → review / tweak → generate graphic")

data_files = sorted(DATA_DIR.glob("*.json"))
brand_files = [f for f in data_files if f.name.startswith("brand_")]
brain_files = [f for f in data_files if f.name.startswith("brain_")]
default_logo = ROOT / "logo.png"

with st.sidebar:
    st.header("Inputs")
    topic = st.text_input("Topic", placeholder="e.g. CreditX deployment speed")
    product_name = st.text_input("Product (optional)", placeholder="e.g. CreditX")
    brand_file = st.selectbox("Brand JSON", brand_files, format_func=lambda p: p.name,
                              index=0 if brand_files else None)
    brain_file = st.selectbox("Brain JSON", brain_files, format_func=lambda p: p.name,
                              index=0 if brain_files else None)
    brand_logo = None
    if brand_file:
        try:
            brand_logo = (json.load(open(brand_file)).get("visual_identity") or {}).get("logo_path")
        except Exception:
            pass
    logo_default = brand_logo if brand_logo and Path(brand_logo).exists() else str(default_logo)
    logo_path = st.text_input("Logo path", value=logo_default)
    propose = st.button("① Propose idea", type="primary")

if not brand_files or not brain_files:
    st.warning("Run **Extraction** first to create brand and brain JSON files in `data/`.")
    st.stop()

def _sig():
    return (str(brand_file), str(brain_file), topic.strip(), product_name.strip())

# ── Step 1: propose ──
if propose:
    if not topic.strip():
        st.error("Enter a topic."); st.stop()
    with st.spinner("Drafting a proposed idea..."):
        try:
            brain = json.load(open(brain_file)); brand = json.load(open(brand_file))
            brief = generate_brief(topic.strip(), brain, brand=brand,
                                   product_name=product_name.strip() or None)
        except Exception as e:
            st.error(str(e)); st.stop()
    if not brief:
        st.error("Couldn't draft an idea — try again."); st.stop()
    st.session_state.proposal = brief
    st.session_state.proposal_sig = _sig()
    st.session_state.pop("result", None)

proposal = st.session_state.get("proposal")

# ── Step 2: review / tweak / regenerate / generate ──
if proposal:
    if st.session_state.get("proposal_sig") != _sig():
        st.warning("Inputs changed since this idea was proposed — click **① Propose idea** to refresh.")

    st.subheader("Proposed idea")
    st.markdown(brief_to_summary(proposal))

    steer = st.text_input("Steer a different idea (optional)",
                          placeholder="e.g. lean more on cost savings")
    if st.button("🔄 Try a different idea"):
        with st.spinner("Drafting a different idea..."):
            new = None
            try:
                brain = json.load(open(brain_file)); brand = json.load(open(brand_file))
                new = generate_brief(topic.strip(), brain, brand=brand,
                                     product_name=product_name.strip() or None,
                                     steer=steer.strip() or None)
            except Exception as e:
                st.warning(f"Regenerate failed, keeping current idea: {e}")
        if new:
            st.session_state.proposal = new
            st.session_state.proposal_sig = _sig()
            st.rerun()

    with st.expander("✏️ Tweak the idea"):
        g = proposal.get("graphic") or {}
        c = proposal.get("caption") or {}
        with st.form("tweak_form"):
            st.markdown("**Graphic copy**")
            headline = st.text_input("Headline", g.get("headline", ""))
            stat_hero = st.text_input("Hero stat", g.get("stat_hero", ""))
            contrast_line = st.text_input("Contrast line", g.get("contrast_line", ""))
            subtext = st.text_input("Subtext", g.get("subtext", ""))
            metrics_text = st.text_area("Metrics (one per line)",
                                        "\n".join(str(m) for m in (g.get("metrics") or [])))
            cta = st.text_input("CTA", g.get("cta", ""))
            design_notes = st.text_area("Layout note (optional)", g.get("design_notes", ""))
            st.markdown("**Caption**")
            hook = st.text_input("Hook", c.get("hook", ""))
            body = st.text_area("Body", c.get("body", ""))
            cap_cta = st.text_input("Caption CTA", c.get("cta", ""))
            applied = st.form_submit_button("Apply tweaks")
        if applied:
            if not (headline.strip() and cta.strip()):
                st.error("Headline and CTA can't be empty.")
            else:
                edited = dict(proposal)
                edited["graphic"] = {**g, "headline": headline, "stat_hero": stat_hero,
                                     "contrast_line": contrast_line, "subtext": subtext,
                                     "metrics": [m.strip() for m in metrics_text.splitlines() if m.strip()],
                                     "cta": cta, "design_notes": design_notes}
                edited["caption"] = {**c, "hook": hook, "body": body, "cta": cap_cta}
                fitted, changes = fit_brief_copy(edited)
                st.session_state.proposal = fitted
                st.session_state.proposal_sig = _sig()
                if changes:
                    st.info("Adjusted to fit:\n" + "\n".join(f"- {ch}" for ch in changes))
                st.rerun()

    st.divider()
    if st.button("② Generate graphic", type="primary"):
        with st.spinner("Generating graphic..."):
            try:
                brand = json.load(open(brand_file))
                st.session_state.result = render_from_brief(
                    st.session_state.proposal, brand, logo_path,
                    product_name=product_name.strip() or None)
            except Exception as e:
                st.error(str(e)); st.stop()

# ── result display ──
result = st.session_state.get("result")
if result:
    st.success("Done!")
    if result.get("design_skill"):
        st.caption(f"Design skill: `{result['design_skill']}` (routed by marketing profile)")
    if result.get("warnings"):
        with st.expander(f"⚠️ {len(result['warnings'])} validation warning(s)", expanded=True):
            for w in result["warnings"]:
                st.markdown(f"- {w}")
    tab_caption, tab_graphic, tab_brief = st.tabs(["Caption", "Graphic", "Brief"])
    with tab_caption:
        st.text_area("LinkedIn post text", result["caption"], height=300)
        st.caption(f"Saved to `{result['caption_path']}`")
    with tab_graphic:
        if result.get("png_path"):
            st.image(result["png_path"])
            with open(result["png_path"], "rb") as f:
                st.download_button("Download PNG (ready to post)", f, file_name="graphic.png", mime="image/png")
            st.caption(f"PNG: `{result['png_path']}` · HTML: `{result['html_path']}`")
            if result.get("draft_png_path"):
                with st.expander("Before / after defect repair"):
                    col_before, col_after = st.columns(2)
                    with col_before:
                        st.markdown("**Before** (initial draft)"); st.image(result["draft_png_path"])
                    with col_after:
                        st.markdown("**After** (shipped)"); st.image(result["png_path"])
            with st.expander("HTML preview"):
                st.components.v1.html(result["html"], height=660, scrolling=True)
        else:
            st.components.v1.html(result["html"], height=680, scrolling=True)
            st.caption(f"Saved to `{result['html_path']}` (PNG render unavailable)")
    with tab_brief:
        st.json(result["brief"])
        st.caption(f"Saved to `{result['brief_path']}`")
elif not proposal:
    st.info("Set a topic and click **① Propose idea** in the sidebar.")
```

- [ ] **Step 6: Compile-check the page**

Run: `./venv/bin/python3 -m py_compile pages/2_Generation.py`
Expected: no output (success).

- [ ] **Step 7: Commit**

```bash
git add layer2_generation/strategy_agent.py pages/2_Generation.py tests/test_summary.py
git commit -m "feat: two-step propose/review/generate Streamlit flow + brief_to_summary"
```

---

### Task 5: Live acceptance — 2 runs each on Finbots, Stripe, Hims

**Files:**
- Test: `tests/live_acceptance.py`

**Interfaces:**
- Consumes: `generate_brief` (Task 2), `render_from_brief` (Task 1) — the exact two halves the Streamlit page drives.

- [ ] **Step 1: Write the acceptance script** — `tests/live_acceptance.py`

```python
"""Live acceptance for the concept-review-gate split. 2 runs each on Finbots
(B2B), Stripe (B2B), Hims (emotional) through generate_brief -> render_from_brief
— the same halves the Streamlit page drives. Needs ANTHROPIC_API_KEY in .env."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from layer2_generation.strategy_agent import generate_brief
from layer2_generation.graphic_generator import render_from_brief

DATA = ROOT / "data"
OUT = DATA / "acceptance"; OUT.mkdir(exist_ok=True)

def finbots_logo():
    p = OUT / "finbots_wordmark.png"
    if not p.exists():
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (260, 64), (255, 255, 255, 0)); d = ImageDraw.Draw(img)
        try: font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
        except Exception: font = ImageFont.load_default()
        d.text((8, 8), "finbots", fill=(0, 188, 112, 255), font=font); img.save(p)
    return str(p)

CASES = [
    ("finbots", "brand_finbotsai.json", "brain_finbotsai_(finbotsai_pte_ltd).json",
     finbots_logo(), "Deploying a live credit scorecard in one day with CreditX"),
    ("stripe", "brand_stripe.json", "brain_stripe.json", str(DATA / "logo_stripe.png"),
     "Recover more revenue automatically with smarter payment retries"),
    ("hims", "brand_hims.json", "brain_hims_&_hers_health,_inc.json", str(DATA / "logo_hims.png"),
     "Skip the waiting room: care that comes to you"),
]

fails = []
for name, bf, brf, logo, topic in CASES:
    brand = json.load(open(DATA / bf)); brain = json.load(open(DATA / brf))
    for i in (1, 2):
        tag = f"{name}_{i}"
        try:
            brief = generate_brief(topic, brain, brand=brand)
            assert brief, "empty brief"
            res = render_from_brief(brief, brand, logo,
                                    html_path=str(OUT / f"{tag}.html"),
                                    png_path=str(OUT / f"{tag}.png"),
                                    brief_path=str(OUT / f"{tag}.brief.json"),
                                    caption_path=str(OUT / f"{tag}.caption.txt"))
            ok = bool(res.get("png_path"))
            print(f"{tag}: skill={res.get('design_skill')} png={'yes' if ok else 'NO'} warnings={res.get('warnings')}")
            if not ok:
                fails.append(tag)
        except Exception as e:
            print(f"{tag}: EXCEPTION {e}"); fails.append(tag)

print("\nRESULT:", "ALL PASS" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
```

- [ ] **Step 2: Run the live acceptance** (long — 6 real generations, run in background if driving via an agent)

Run: `./venv/bin/python3 tests/live_acceptance.py`
Expected: 6 lines each showing a `png=yes`; Finbots + Stripe show `skill=marketing_graphic_skill.md`, Hims shows `skill=brand_canvas_skill.md`; final line `RESULT: ALL PASS`; exit code 0.

- [ ] **Step 3: Manual Streamlit walkthrough** (human check)

Run: `streamlit run streamlit_app.py`, open **Generation**, then verify:
1. Propose idea → the concept summary appears, no graphic yet.
2. Tweak a field → Apply tweaks → the summary updates (and shows any "Adjusted to fit" note).
3. Try a different idea (with a steer) → a visibly different proposal.
4. Generate graphic → the graphic + before/after view render.
5. Change the topic after proposing → the "inputs changed — propose again" warning shows.

- [ ] **Step 4: Commit**

```bash
git add tests/live_acceptance.py
git commit -m "test: live acceptance for concept-review gate (2x Finbots/Stripe/Hims)"
```

---

## Notes

- `data/acceptance/` output is gitignored (under `data/`).
- After merging, update CLAUDE.md's Layer 2 description to mention the two-step Generation flow and `render_from_brief` / `generate_brief(steer=)` / `fit_brief_copy`.
- **Deviation from spec (unsaved-tweaks hint):** the spec proposed a "unsaved tweaks — Apply first" hint. It is intentionally omitted: the tweak fields live inside an `st.form`, so their values are only readable on the form's "Apply tweaks" submit — a reliable live "you have unsaved edits" indicator isn't available. The form boundary makes the behavior explicit instead (edits only take effect via Apply; Generate always renders the last applied proposal).
