# Ad-Project — AI Marketing Content Pipeline

Company website URL + a topic → ready-to-post LinkedIn caption + branded graphic (HTML and a rendered 1200x627 PNG). Solo project, Streamlit UI, everything runs locally.

## Architecture (two layers, deliberately separate)

**Layer 1 — Extraction** (`layer1_extraction/`): understand the company once, reuse for many posts.
- `extract_brand.py` — homepage scrape → `data/brand_<slug>.json`: visual identity (colors, fonts via a pre-truncation font-evidence pass, logo auto-fetched and normalized to PNG) + `marketing_profile` (business model, rational-vs-emotional persuasion, content density [`minimal | standard`], CTA style). The profile drives everything downstream.
- `extract_brain.py` — Firecrawl `map()` → heuristic junk filter → Haiku relevance-ranks pages → `batch_scrape` top N → one extraction call → `data/brain_<slug>.json` (products, metrics, quotes, pricing, pain points, promises...). `brain_to_context()` does topic-aware selection across all pools in ONE Haiku call.
- `enrich_brain.py` — PDFs/decks/notes (PDF sent natively as document blocks) extracted against the same schema, then LLM-merged into the existing brain with semantic dedupe. Merge failure never destroys the existing brain.

**Layer 2 — Generation** (`layer2_generation/`):
- `strategy_agent.py` — topic + brain + marketing profile → structured brief (caption + graphic copy with hard word limits).
- `graphic_generator.py` — the staged pipeline: **junior draft** (design skill routed by marketing profile) → text validation (exact copy, canvas size, visible-word budget; regenerate once on failure) → **defect gate** (vision inspection of the rendered PNG for overlap/clipping) → surgical repair if needed. Every run also saves a pre-repair draft (`*_draft.html`/`*_draft.png`) beside the final output. (A senior-designer *enhance* stage was removed — side-by-side testing showed it worsened outputs by adding overlaps; the dormant code stays in `review.review_and_enhance` for easy restoration.)
- `review.py` — "the generator writes HTML blind; this module is its eyes": Playwright screenshot, defect detection, repair. (`review_and_enhance`, the old senior-review pass, is retained but unused.)

**Shared core**: `llm.py` — the ONLY place API clients and model IDs live (`MODEL_HEAVY` / `MODEL_LIGHT`). Change a model here, nowhere else. All fence-strip/JSON-parse/retry logic is `llm.complete()` / `llm.complete_json()`.

**Skills** (`skills/*.md`) — the prompt tuning surface, loaded as system prompts:
- `marketing_graphic_skill.md` — distinctive, production-grade graphics for rational/B2B brands (the restored original `SKILL2`; won a multi-brand Finbots/Ramp/Stripe bake-off over the old data-forward skill).
- `brand_canvas_skill.md` — art-directed, philosophy-first graphics (emotional/minimal/D2C/prosumer brands).
- Routing between them is `_choose_design_skill()` in graphic_generator, keyed off the brand's `marketing_profile`.
- `frontend_design_skill.md` — the previous data-forward B2B skill, now retired from routing (kept only as a defensive fallback in `_build_system_prompt`).
- `linkedin_strategy_skill.md` — the strategist persona (profile-adaptive, 6 post types)
- `senior_designer_skill.md` — the review agent persona

## Running

```bash
streamlit run streamlit_app.py          # UI: Extraction page + Generation page
python layer1_extraction/extract_brand.py <url>
python layer1_extraction/extract_brain.py <url>
python layer1_extraction/enrich_brain.py data/brain_x.json deck.pdf notes.md
python layer2_generation/review.py output.html   # render + defect-check any graphic
```

- Interpreter: `./venv/bin/python3` — **Python 3.9**: `list[str]` annotations are fine, `X | Y` unions are NOT (this has bitten before).
- `.env` at repo root: `ANTHROPIC_API_KEY`, `FIRECRAWL_API_KEY`.
- Playwright Chromium required for rendering: `playwright install chromium` (deps pinned in requirements.txt).
- **Restart Streamlit after code changes** — the running server caches imported modules; stale-code runs have caused false bug reports before.

## Conventions that matter

- **Prompts are tuned and live-verified — treat them as tested behavior.** Refactor plumbing freely; change prompt wording deliberately and re-verify with a live run.
- **Verify live before committing.** The project pattern is a real API run (extraction or full generation) as the acceptance test — mocks have repeatedly missed real-model behavior (fence-wrapping, invented copy, layout collisions).
- **Graceful degradation everywhere.** A failed enhancement/merge/fetch returns the previous good state and prints; it never raises through the pipeline or destroys existing data.
- **Copy discipline is enforced in code, not hoped for in prompts**: metrics hard-capped at 2, visible-word budget checked against the brief, exact headline/CTA verified (markup/entity tolerant).
- **The logo travels as a `__LOGO_BASE64__` placeholder** through generation and is substituted afterward — never ask the model to transcribe base64.
- `data/` is gitignored: brand/brain JSONs, per-brand logos (`logo_<slug>.png`), outputs. Brains carry a code-managed `sources` provenance list — never let the model write it.
- Print-based logging and per-module `__main__` CLIs are intentional (right-sized for solo use).

## Git

- `main` is canonical. `main-legacy` preserves the pre-rewrite June version. `ig_strat_test` and `worktree-layer2-enhance` hold unmerged Instagram-routing experiments (unique work — don't delete casually); other branches are redundant with main.
- Session workflow: build on a temp branch in a worktree, verify live, commit, `git merge --ff-only` into the target branch. Keep merges fast-forward.
- **Remote**: `origin` → github.com/shivupl/ad-project. Local `main` is canonical; push to the remote only when explicitly asked — never auto-push to remote `main`.

## Known gaps / roadmap

- Inline-SVG logos (e.g. Hims) aren't auto-fetched — only `logo_url` images are; the SVG→PNG converter exists in `extract_brand.py`, it just isn't wired to inline page SVGs.
- Instagram/platform routing designed but unmerged (see `ig_strat_test` branch for the strategy skill).
- Very large multi-product sites (Adobe-scale) exceed the `map(limit=100)` / `max_pages` defaults — the brain samples rather than covers them.
- Brand-guideline-PDF enrichment for visual identity (brain-only enrichment exists today).
