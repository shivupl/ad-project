import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anthropic
import json
import os
import re
from dotenv import load_dotenv

from layer1_extraction.extract_brain import brain_to_context
from layer1_extraction.extract_brand import marketing_profile_to_context
from paths import LINKEDIN_STRATEGY_SKILL

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

STRATEGY_SYSTEM_PROMPT = LINKEDIN_STRATEGY_SKILL.read_text()

DEFAULT_PROFILE_LINE = "MARKETING PROFILE: Not provided — default to a professional, metric-driven B2B register."


def generate_brief(topic: str, brain: dict, brand: dict = None, product_name: str = None) -> dict:
    """
    Takes a user topic + brain JSON (+ optional brand JSON for its marketing
    profile) → returns structured post brief with separate 'caption' (LinkedIn
    post text) and 'graphic' (image content) sections.
    """

    brain_context = brain_to_context(brain, product_name=product_name, topic=topic)
    profile_block = marketing_profile_to_context(brand) if brand else ""
    if not profile_block:
        profile_block = DEFAULT_PROFILE_LINE

    user_message = f"""
COMPANY KNOWLEDGE:
{brain_context}

{profile_block}

USER TOPIC:
{topic}

Generate the best possible LinkedIn post brief for this topic using only facts from the company knowledge above.
Adapt post type, register, and copy density to the MARKETING PROFILE.
Remember: caption and graphic are separate artifacts with separate word budgets.
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=STRATEGY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'^```\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Raw: {raw[:300]}")
        return {}


def brief_to_caption(brief: dict) -> str:
    """Converts the caption section into plain text ready to paste into LinkedIn."""
    caption = brief.get("caption", {})

    hook = caption.get("hook", "")
    body = caption.get("body", "")
    cta = caption.get("cta", "")

    return f"{hook}\n\n{body}\n\n{cta}"


def brief_to_post_content(brief: dict, logo_b64: str) -> str:
    """Converts the graphic section into the prompt string for graphic generation."""
    graphic = brief.get("graphic", {})

    metrics_str = "\n".join([f"  · {m}" for m in graphic.get("metrics", [])])

    stat_line = f'- Stat hero: "{graphic["stat_hero"]}"' if graphic.get("stat_hero") else ""
    contrast_line = f'- Contrast line: "{graphic["contrast_line"]}"' if graphic.get("contrast_line") else ""

    return f"""Embed this exact logo in the HTML as a base64 data URI:
<img src="data:image/png;base64,{logo_b64}" alt="logo" style="max-height:36px" />

POST TYPE: {brief.get('post_type', '').replace('_', ' ').title()}
DESIGN NOTES: {graphic.get('design_notes', '')}

EXACT COPY — do not change any wording:
- Headline: "{graphic.get('headline', '')}"
{stat_line}
{contrast_line}
- Subtext: "{graphic.get('subtext', '')}"
- Supporting metrics:
{metrics_str}
- CTA: "{graphic.get('cta', '')}"
"""


if __name__ == "__main__":
    import sys
    import base64

    brain_file = sys.argv[1] if len(sys.argv) > 1 else input("Brain JSON path: ").strip()
    topic = sys.argv[2] if len(sys.argv) > 2 else input("What do you want to post about? ").strip()
    product_name = sys.argv[3] if len(sys.argv) > 3 else None
    logo_path = sys.argv[4] if len(sys.argv) > 4 else input("Logo path: ").strip()
    brand_file = sys.argv[5] if len(sys.argv) > 5 else None

    with open(brain_file) as f:
        brain = json.load(f)

    brand = None
    if brand_file:
        with open(brand_file) as f:
            brand = json.load(f)

    with open(logo_path, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode()

    print(f"\nGenerating brief for topic: '{topic}'...")
    brief = generate_brief(topic, brain, brand=brand, product_name=product_name)

    if brief:
        print("\n--- FULL BRIEF ---")
        print(json.dumps(brief, indent=2))

        print("\n--- LINKEDIN CAPTION (post text) ---")
        print(brief_to_caption(brief))

        print("\n--- GRAPHIC CONTENT ---")
        print(brief_to_post_content(brief, logo_b64))
