import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import base64
import html as html_lib
import json
import os
import re

import anthropic
from dotenv import load_dotenv

from layer1_extraction.extract_brand import brand_to_prompt
from paths import DATA_DIR, FRONTEND_DESIGN_SKILL, ROOT
from layer2_generation.render_graphic import html_to_png, review_graphic_png
from layer2_generation.strategy_agent import brief_to_caption, brief_to_post_content, generate_brief, validate_brief

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

LOGO_PLACEHOLDER = "__LOGO_BASE64__"
CANVAS_WIDTH = 1200
CANVAS_HEIGHT = 627
# 3 attempts: room for one text-side correction and one visual-side correction
MAX_GENERATION_ATTEMPTS = 3
# Allowance on top of the brief's own copy for small labels (company name, url,
# chip captions) — anything past this means the model invented paragraphs.
EXTRA_WORDS_ALLOWANCE = 25


def load_logo_b64(logo_path: str) -> str:
    with open(logo_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _build_system_prompt(correction: str = None) -> str:
    skill = FRONTEND_DESIGN_SKILL.read_text()
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


def generate_graphic_html(
    brand_prompt: str,
    post_content: str,
    logo_b64: str,
    correction: str = None,
) -> str:
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=8000,
        thinking={"type": "disabled"},
        system=_build_system_prompt(correction),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": logo_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": brand_prompt + "\n\n" + post_content,
                    },
                ],
            }
        ],
    )

    if response.stop_reason == "max_tokens":
        raise RuntimeError("Graphic generation hit max_tokens — output would be broken HTML.")

    html = response.content[0].text.strip()
    html = re.sub(r'^```(?:html)?\s*', '', html)
    html = re.sub(r'\s*```$', '', html)
    return html


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


def validate_graphic(html: str, brief: dict) -> list[str]:
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


def generate_graphic(brand_prompt: str, post_content: str, logo_b64: str, brief: dict, png_path: str = None) -> tuple:
    """Generate the graphic HTML with two validation stages, retrying with
    corrective feedback on failure:
      1. text checks (exact copy, canvas size, word budget, truncation)
      2. visual QA — render to PNG headlessly, then a vision call inspects the
         actual pixels for overlap/clipping/illegibility (the failure class no
         text check can see)
    Returns (final_html_with_logo, warnings)."""
    correction = None
    html_final, issues = "", []

    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        html = generate_graphic_html(brand_prompt, post_content, logo_b64, correction=correction)
        issues = validate_graphic(html, brief)
        html_final = html.replace(LOGO_PLACEHOLDER, logo_b64)

        if not issues and png_path:
            if html_to_png(html_final, png_path):
                defects = review_graphic_png(png_path)
                issues = [f"The rendered image shows: {d}" for d in defects]

        if not issues:
            break
        if attempt < MAX_GENERATION_ATTEMPTS:
            print(f"Graphic validation failed (attempt {attempt}), retrying with corrections: {issues}")
            correction = "\n".join(f"- {i}" for i in issues)

    # If the last attempt failed at the text stage, the PNG on disk is stale —
    # re-render so the saved PNG always matches the saved HTML.
    if issues and png_path:
        html_to_png(html_final, png_path)

    return html_final, issues


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
    """Full pipeline: topic → strategy brief → caption + HTML graphic + PNG."""
    caption_path = caption_path or str(DATA_DIR / "caption.txt")
    html_path = html_path or str(DATA_DIR / "output.html")
    brief_path = brief_path or str(DATA_DIR / "brief.json")
    png_path = png_path or str(DATA_DIR / "output.png")

    with open(brand_path) as f:
        profile = json.load(f)
    with open(brain_path) as f:
        brain = json.load(f)

    logo_b64 = load_logo_b64(logo_path)
    brand_prompt = brand_to_prompt(profile)

    brief = generate_brief(topic, brain, brand=profile, product_name=product_name)
    if not brief:
        raise RuntimeError("Strategy agent failed — no brief generated")

    caption = brief_to_caption(brief)
    post_content = brief_to_post_content(brief, LOGO_PLACEHOLDER)

    with open(brief_path, "w") as f:
        json.dump(brief, f, indent=2)
    with open(caption_path, "w") as f:
        f.write(caption)

    html, warnings = generate_graphic(brand_prompt, post_content, logo_b64, brief, png_path=png_path)
    warnings = validate_brief(brief) + warnings
    with open(html_path, "w") as f:
        f.write(html)

    return {
        "brief": brief,
        "caption": caption,
        "post_content": post_content,
        "html": html,
        "warnings": warnings,
        "caption_path": caption_path,
        "html_path": html_path,
        "brief_path": brief_path,
        "png_path": png_path if os.path.exists(png_path) else None,
    }


if __name__ == "__main__":
    topic = "CreditX deployment speed"
    product_name = "CreditX"

    result = run(
        topic=topic,
        brand_path=str(DATA_DIR / "brand_finbotsai.json"),
        brain_path=str(DATA_DIR / "brain_finbotsai.json"),
        logo_path=str(ROOT / "logo.png"),
        product_name=product_name,
    )

    print("--- LINKEDIN CAPTION ---")
    print(result["caption"])
    print("\n--- GRAPHIC CONTENT ---")
    print(result["post_content"])
    print(f"\nDone — open {result['html_path']} in browser")
