import anthropic
import json
import os
import re
from dotenv import load_dotenv
from extract_brain import brain_to_context

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# SYSTEM PROMPT (linkedin strategy skill) — loaded from skill file
STRATEGY_SYSTEM_PROMPT = open("linkedin_strategy_skill.md").read()


# ─────────────────────────────────────────────
# GENERATE POST BRIEF
# ─────────────────────────────────────────────

def generate_brief(topic: str, brain: dict, product_name: str = None) -> dict:
    """
    Takes a user topic + brain JSON → returns structured post brief
    with separate 'caption' (LinkedIn post text) and 'graphic' (image content) sections.
    """

    brain_context = brain_to_context(brain, product_name=product_name)

    user_message = f"""
COMPANY KNOWLEDGE:
{brain_context}

USER TOPIC:
{topic}

Generate the best possible LinkedIn post brief for this topic using only facts from the company knowledge above.
Remember: caption and graphic are separate artifacts with separate word budgets.
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=STRATEGY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
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


# ─────────────────────────────────────────────
# FORMAT: caption → plain text ready to post on LinkedIn
# ─────────────────────────────────────────────

def brief_to_caption(brief: dict) -> str:
    """Converts the caption section into plain text ready to paste into LinkedIn."""
    caption = brief.get("caption", {})

    hook = caption.get("hook", "")
    body = caption.get("body", "")
    cta  = caption.get("cta", "")

    return f"{hook}\n\n{body}\n\n{cta}"


# ─────────────────────────────────────────────
# FORMAT: graphic → post_content string for app.py
# ─────────────────────────────────────────────

def brief_to_post_content(brief: dict, logo_b64: str) -> str:
    """
    Converts the graphic section into the post_content string
    that gets passed directly into app.py for graphic generation.
    """
    graphic = brief.get("graphic", {})

    metrics_str = "\n".join([f"  · {m}" for m in graphic.get("metrics", [])])

    stat_line     = f'- Stat hero: "{graphic["stat_hero"]}"' if graphic.get("stat_hero") else ""
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


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import base64

    brain_file   = sys.argv[1] if len(sys.argv) > 1 else input("Brain JSON path: ").strip()
    topic        = sys.argv[2] if len(sys.argv) > 2 else input("What do you want to post about? ").strip()
    product_name = sys.argv[3] if len(sys.argv) > 3 else None
    logo_path    = sys.argv[4] if len(sys.argv) > 4 else input("Logo path: ").strip()

    with open(brain_file) as f:
        brain = json.load(f)

    with open(logo_path, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode()

    print(f"\nGenerating brief for topic: '{topic}'...")
    brief = generate_brief(topic, brain, product_name)

    if brief:
        print("\n--- FULL BRIEF ---")
        print(json.dumps(brief, indent=2))

        print("\n--- LINKEDIN CAPTION (post text) ---")
        print(brief_to_caption(brief))

        print("\n--- GRAPHIC CONTENT (for app.py) ---")
        print(brief_to_post_content(brief, logo_b64))
