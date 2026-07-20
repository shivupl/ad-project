import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json

import llm
from layer1_extraction.extract_brain import brain_to_context
from layer1_extraction.extract_brand import marketing_profile_to_context
from paths import LINKEDIN_STRATEGY_SKILL

STRATEGY_SYSTEM_PROMPT = LINKEDIN_STRATEGY_SKILL.read_text()

DEFAULT_PROFILE_LINE = "MARKETING PROFILE: Not provided — default to a professional, metric-driven B2B register."


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


# ─────────────────────────────────────────────
# Brief validation and conversion
# ─────────────────────────────────────────────

GRAPHIC_WORD_LIMITS = {"headline": 8, "contrast_line": 8, "subtext": 12, "cta": 5}
MAX_GRAPHIC_METRICS = 2
METRIC_WORD_LIMIT = 6


def validate_brief(brief: dict) -> list:
    """Checks the graphic section against the hard word-count limits defined in
    the strategy skill. Returns human-readable warnings (empty = clean)."""
    warnings = []
    graphic = brief.get("graphic", {})

    for field, limit in GRAPHIC_WORD_LIMITS.items():
        value = (graphic.get(field) or "").strip()
        if value:
            words = len(value.split())
            if words > limit:
                warnings.append(f'graphic.{field} is {words} words (limit {limit}): "{value}"')

    metrics = graphic.get("metrics") or []
    if len(metrics) > MAX_GRAPHIC_METRICS:
        warnings.append(f"graphic.metrics has {len(metrics)} items (limit {MAX_GRAPHIC_METRICS}) — extra items are dropped from the graphic")
    for m in metrics[:MAX_GRAPHIC_METRICS]:
        words = len(str(m).split())
        if words > METRIC_WORD_LIMIT:
            warnings.append(f'graphic.metrics item is {words} words (limit {METRIC_WORD_LIMIT}): "{m}"')

    return warnings


def brief_to_caption(brief: dict) -> str:
    """Converts the caption section into plain text ready to paste into LinkedIn."""
    caption = brief.get("caption", {})
    return f"{caption.get('hook', '')}\n\n{caption.get('body', '')}\n\n{caption.get('cta', '')}"


def brief_to_post_content(brief: dict, logo_b64: str) -> str:
    """Converts the graphic section into the prompt string for graphic generation.
    Metrics are hard-capped in code — richer brains produce more material, and
    a crammed graphic fails the squint test no matter how good the facts are."""
    graphic = brief.get("graphic", {})

    metrics = (graphic.get("metrics") or [])[:MAX_GRAPHIC_METRICS]
    metrics_str = "\n".join([f"  · {m}" for m in metrics]) or "  (none)"

    stat_line = f'- Stat hero: "{graphic["stat_hero"]}"' if graphic.get("stat_hero") else ""
    contrast_line = f'- Contrast line: "{graphic["contrast_line"]}"' if graphic.get("contrast_line") else ""

    return f"""Embed this exact logo in the HTML as a base64 data URI:
<img src="data:image/png;base64,{logo_b64}" alt="logo" style="max-height:36px" />

POST TYPE: {brief.get('post_type', '').replace('_', ' ').title()}
DESIGN NOTES: {graphic.get('design_notes', '')}

EXACT COPY — this is ALL the text allowed on the graphic. Reproduce it
character-for-character. Do NOT add any other copy: no extra paragraphs, no
additional bullet points, no explanatory sentences, no taglines you invent.
The only text allowed beyond this list is the company name/URL as a small label.
- Headline: "{graphic.get('headline', '')}"
{stat_line}
{contrast_line}
- Subtext: "{graphic.get('subtext', '')}"
- Supporting metrics (max {MAX_GRAPHIC_METRICS}, render as short chips, not sentences):
{metrics_str}
- CTA: "{graphic.get('cta', '')}"
"""


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    brain_file = sys.argv[1] if len(sys.argv) > 1 else input("Brain JSON path: ").strip()
    topic = sys.argv[2] if len(sys.argv) > 2 else input("What do you want to post about? ").strip()
    product_name = sys.argv[3] if len(sys.argv) > 3 else None
    brand_file = sys.argv[4] if len(sys.argv) > 4 else None

    with open(brain_file) as f:
        brain = json.load(f)

    brand = None
    if brand_file:
        with open(brand_file) as f:
            brand = json.load(f)

    print(f"\nGenerating brief for topic: '{topic}'...")
    brief = generate_brief(topic, brain, brand=brand, product_name=product_name)

    if brief:
        print("\n--- FULL BRIEF ---")
        print(json.dumps(brief, indent=2))
        print("\n--- CAPTION ---")
        print(brief_to_caption(brief))
        for w in validate_brief(brief):
            print(f"warning: {w}")
