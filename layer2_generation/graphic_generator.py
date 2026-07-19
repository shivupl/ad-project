import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import base64
import html as html_lib
import json
import os
import re
import shutil

import llm
from layer1_extraction.extract_brand import brand_to_prompt
from layer2_generation.review import (
    CANVAS_HEIGHT, CANVAS_WIDTH, find_defects, html_to_png, repair_html,
)
from layer2_generation.strategy_agent import brief_to_caption, brief_to_post_content, generate_brief, validate_brief
from paths import BRAND_CANVAS_SKILL, DATA_DIR, FRONTEND_DESIGN_SKILL, MARKETING_GRAPHIC_SKILL, ROOT

LOGO_PLACEHOLDER = "__LOGO_BASE64__"
# Allowance on top of the brief's own copy for small labels (company name, url,
# chip captions) — anything past this means the model invented paragraphs.
EXTRA_WORDS_ALLOWANCE = 25


def load_logo_b64(logo_path: str) -> str:
    with open(logo_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _choose_design_skill(brand: dict):
    """Route the design skill by marketing profile: the visually-led canvas
    skill for emotional/minimal/D2C/prosumer brands, and the marketing-graphic
    skill (the original SKILL2, restored after a multi-brand bake-off on
    Finbots/Ramp/Stripe) for rational B2B and everything else."""
    mp = brand.get("marketing_profile") or {}
    if (mp.get("persuasion_mode") == "emotional"
            or mp.get("content_density") == "minimal"
            or mp.get("business_model") in ("d2c_consumer", "prosumer_creative")):
        return BRAND_CANVAS_SKILL
    return MARKETING_GRAPHIC_SKILL


# ─────────────────────────────────────────────
# STEP 1: Junior draft
# ─────────────────────────────────────────────

def _build_system_prompt(correction: str = None, skill_path=None) -> str:
    skill = (skill_path or FRONTEND_DESIGN_SKILL).read_text()
    correction_block = f"\n\nFIX THESE SPECIFIC PROBLEMS FROM YOUR LAST ATTEMPT:\n{correction}\n" if correction else ""

    return f"""{skill}

You are generating a single marketing graphic as a self-contained HTML file for a social post.

CRITICAL — CANVAS SIZE:
- The outer container MUST be exactly {CANVAS_WIDTH}px wide by {CANVAS_HEIGHT}px tall — a wide horizontal rectangle (LinkedIn format).
- Do not default to a square 1080x1080 canvas out of habit. Design horizontally: {CANVAS_HEIGHT}px of vertical space is tight, favor left/right splits over tall stacks.
- Set explicit width: {CANVAS_WIDTH}px; height: {CANVAS_HEIGHT}px; overflow: hidden on the outer wrapper.

CRITICAL — COPY DISCIPLINE (this is a social graphic, not a slide):
- The EXACT COPY list in the brief is the ONLY text allowed on the canvas, reproduced character-for-character.
- Do NOT write any additional copy: no explanatory paragraphs, no extra bullets, no invented taglines. A viewer must grasp the graphic in 2 seconds — every extra word you add breaks it.
- The only permitted additions are tiny labels: the company name/URL and short chip captions.

CRITICAL — LOGO:
- A logo image is attached for layout/color reference only. Do NOT transcribe its base64 data yourself.
- Where the logo belongs, emit exactly: <img src="data:image/png;base64,{LOGO_PLACEHOLDER}" alt="logo" style="height:32px;width:auto" />
- The placeholder text `{LOGO_PLACEHOLDER}` must appear verbatim exactly once.

OUTPUT RULES:
- Output ONLY raw HTML — no markdown, no backticks, no explanation.
- Self-contained except the logo placeholder — no other external images. Google Fonts via @import is allowed.
- Everything must fit the {CANVAS_WIDTH}x{CANVAS_HEIGHT} canvas without clipping or scrolling.
- Output the complete HTML file including the closing </html> tag.
{correction_block}"""


def generate_graphic_html(brand_prompt: str, post_content: str, logo_b64: str,
                          correction: str = None, skill_path=None) -> str:
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": logo_b64}},
        {"type": "text", "text": brand_prompt + "\n\n" + post_content},
    ]
    return llm.complete(content, max_tokens=8000, system=_build_system_prompt(correction, skill_path))


# ─────────────────────────────────────────────
# STEP 2: Text-side validation (fast, deterministic)
# ─────────────────────────────────────────────

_DECORATIVE_CHARS = re.compile(r'[→←↑↓➜➔›»·]')


def _visible_text(html: str) -> str:
    """Rendered text only: styles/scripts/tags stripped, entities decoded."""
    text = re.sub(r'<(style|script)[^>]*>.*?</\1>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_lib.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def _normalize_text(text: str) -> str:
    """For copy comparison: markup, entities and decorative glyphs ignored."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_lib.unescape(text)
    text = _DECORATIVE_CHARS.sub(' ', text)
    return re.sub(r'\s+', ' ', text).strip().lower()


def validate_graphic(html: str, brief: dict) -> list:
    """Structural checks against hard constraints. Returns issues (empty = clean)."""
    issues = []
    graphic = brief.get("graphic", {})

    if not html.lstrip().lower().startswith(("<!doctype", "<html")):
        issues.append("Output does not start with <!DOCTYPE>/<html> — leftover commentary or fences.")
    if not html.rstrip().lower().endswith("</html>"):
        issues.append("Output does not end with </html> — likely truncated.")

    if not (re.search(rf"width:\s*{CANVAS_WIDTH}px", html) and re.search(rf"height:\s*{CANVAS_HEIGHT}px", html)):
        issues.append(f"Canvas is not declared as exactly {CANVAS_WIDTH}px x {CANVAS_HEIGHT}px — this must be a wide rectangle, not a square.")

    visible_norm = _normalize_text(html)
    for field in ("headline", "cta"):
        value = (graphic.get(field) or "").strip()
        if value and _normalize_text(value) not in visible_norm:
            issues.append(f'The exact "{field}" copy — "{value}" — does not appear verbatim in the output.')

    if LOGO_PLACEHOLDER not in html:
        issues.append(f"Logo placeholder `{LOGO_PLACEHOLDER}` is missing — logo will not render.")

    # Copy-discipline check: total visible words must stay close to the brief's own copy.
    copy_fields = [graphic.get(f) or "" for f in ("headline", "stat_hero", "contrast_line", "subtext", "cta")]
    copy_fields += list((graphic.get("metrics") or [])[:2])
    budget = sum(len(str(v).split()) for v in copy_fields) + EXTRA_WORDS_ALLOWANCE
    visible_words = len(_visible_text(html).split())
    if visible_words > budget:
        issues.append(
            f"Too much text on the canvas: {visible_words} visible words vs a budget of {budget}. "
            f"Remove ALL copy that is not in the EXACT COPY list — no paragraphs, no extra bullets."
        )

    return issues


# ─────────────────────────────────────────────
# STEP 3: Orchestration — draft → defect gate
# ─────────────────────────────────────────────

def generate_graphic(brand_prompt: str, post_content: str, logo_b64: str, brief: dict,
                     png_path: str = None, skill_path=None,
                     draft_html_path: str = None, draft_png_path: str = None) -> tuple:
    """Draft → defect-gate pipeline:
      1. Draft the graphic; text checks regenerate once if broken.
      2. Defect gate: vision inspection of the rendered PNG; overlap/clipping
         is repaired surgically without touching the design.
    (The senior-designer enhance stage was removed — side-by-side testing
    showed it made outputs worse. See review.review_and_enhance to restore.)
    When draft paths are given, the pre-repair version is saved there so every
    run has a before/after pair (identical when no repair was needed).
    Returns (final_html_with_logo, warnings, critique) — critique is always
    None now, kept for interface stability."""

    def substitute(h):
        return h.replace(LOGO_PLACEHOLDER, logo_b64)

    def snapshot_draft(h):
        if draft_html_path:
            with open(draft_html_path, "w") as f:
                f.write(substitute(h))
        if draft_png_path and png_path and os.path.exists(png_path):
            shutil.copyfile(png_path, draft_png_path)

    # ── Stage 1: junior draft ──
    html = generate_graphic_html(brand_prompt, post_content, logo_b64, skill_path=skill_path)
    issues = validate_graphic(html, brief)
    if issues:
        print(f"Junior draft failed text checks, regenerating: {issues}")
        html = generate_graphic_html(brand_prompt, post_content, logo_b64,
                                     correction="\n".join(f"- {i}" for i in issues),
                                     skill_path=skill_path)
        issues = validate_graphic(html, brief)
        if issues:
            html_final = substitute(html)
            if png_path:
                html_to_png(html_final, png_path)
            snapshot_draft(html)
            return html_final, issues, None

    if not png_path or not html_to_png(substitute(html), png_path):
        snapshot_draft(html)
        return substitute(html), [], None

    snapshot_draft(html)

    # ── Stage 2: defect gate + surgical repair ──
    defects = find_defects(png_path)
    if defects:
        print(f"Final render has defects, repairing in place: {defects}")
        repaired = repair_html(html, png_path, defects)
        if not validate_graphic(repaired, brief):
            html = repaired
        html_to_png(substitute(html), png_path)
        defects = find_defects(png_path)

    issues = [f"The rendered image shows: {d}" for d in defects]
    return substitute(html), issues, None


# ─────────────────────────────────────────────
# STEP 4: Full pipeline entry point
# ─────────────────────────────────────────────

def run(
    topic: str,
    brand_path: str,
    brain_path: str,
    logo_path: str,
    product_name: str = None,
    caption_path: str = None,
    html_path: str = None,
    brief_path: str = None,
    png_path: str = None,
) -> dict:
    """Full pipeline: topic → strategy brief → caption + HTML graphic + PNG.
    Also saves the pre-repair draft next to the final output
    (*_draft.html / *_draft.png) so every run has a before/after pair."""
    caption_path = caption_path or str(DATA_DIR / "caption.txt")
    html_path = html_path or str(DATA_DIR / "output.html")
    brief_path = brief_path or str(DATA_DIR / "brief.json")
    png_path = png_path or str(DATA_DIR / "output.png")
    draft_html_path = str(Path(html_path).with_name(Path(html_path).stem + "_draft.html"))
    draft_png_path = str(Path(png_path).with_name(Path(png_path).stem + "_draft.png"))
    for stale in (draft_html_path, draft_png_path):
        Path(stale).unlink(missing_ok=True)

    with open(brand_path) as f:
        brand = json.load(f)
    with open(brain_path) as f:
        brain = json.load(f)

    logo_b64 = load_logo_b64(logo_path)
    brand_prompt = brand_to_prompt(brand)

    brief = generate_brief(topic, brain, brand=brand, product_name=product_name)
    if not brief:
        raise RuntimeError("Strategy agent failed — no brief generated")

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


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    result = run(
        topic="CreditX deployment speed",
        brand_path=str(DATA_DIR / "brand_finbotsai.json"),
        brain_path=str(DATA_DIR / "brain_finbotsai.json"),
        logo_path=str(ROOT / "logo.png"),
        product_name="CreditX",
    )

    print("--- CAPTION ---")
    print(result["caption"])
    if result["critique"]:
        print("\n--- SENIOR REVIEW ---")
        print(result["critique"])
    for w in result["warnings"]:
        print(f"warning: {w}")
    print(f"\nDone — PNG: {result['png_path']}  HTML: {result['html_path']}")
    print(f"Pre-review draft — PNG: {result['draft_png_path']}  HTML: {result['draft_html_path']}")
