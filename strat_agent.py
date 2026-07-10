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


# GENERATE POST BRIEF
def generate_brief(topic: str, brain: dict, product_name: str = None) -> dict:
    """
    Takes a user topic + brain JSON → returns structured post brief.

    Args:
        topic: what the user wants to post about e.g. "CreditX deployment speed"
        brain: loaded brain JSON
        product_name: optional product to filter brain context e.g. "CreditX"
    """

    brain_context = brain_to_context(brain, product_name=product_name)

    user_message = f"""
    COMPANY KNOWLEDGE:
    {brain_context}

    USER TOPIC:
    {topic}

    Generate the best possible LinkedIn post brief for this topic using only facts from the company knowledge above.
    """

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
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
# FORMAT BRIEF → POST CONTENT STRING
def brief_to_post_content(brief: dict, logo_b64: str) -> str:
    """
    Converts structured brief into the post_content string
    that gets passed directly into app.py for graphic generation.
    """

    metrics_str = "\n".join([f"  · {m}" for m in brief.get("metrics", [])])

    stat_line    = f'- Stat hero: "{brief["stat_hero"]}"' if brief.get("stat_hero") else ""
    contrast_line = f'- Contrast line: "{brief["contrast_line"]}"' if brief.get("contrast_line") else ""

    return f"""Embed this exact logo in the HTML as a base64 data URI:
            <img src="data:image/png;base64,{logo_b64}" alt="logo" style="max-height:36px" />

            POST TYPE: {brief.get('post_type', '').replace('_', ' ').title()}
            DESIGN NOTES: {brief.get('design_notes', '')}

            EXACT COPY — do not change any wording:
            - Headline: "{brief.get('headline', '')}"
            {stat_line}
            {contrast_line}
            - Subtext: "{brief.get('subtext', '')}"
            - Supporting metrics:
            {metrics_str}
            - CTA: "{brief.get('cta', '')}"
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
        print("\n--- BRIEF ---")
        print(json.dumps(brief, indent=2))

        print("\n--- POST CONTENT (ready for app.py) ---")
        print(brief_to_post_content(brief, logo_b64))