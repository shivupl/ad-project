import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import base64
import json
import os
import re

import anthropic
from dotenv import load_dotenv

from layer1_extraction.extract_brand import brand_to_prompt
from paths import DATA_DIR, FRONTEND_DESIGN_SKILL, ROOT
from layer2_generation.strategy_agent import brief_to_caption, brief_to_post_content, generate_brief

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def load_logo_b64(logo_path: str) -> str:
    with open(logo_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def generate_graphic_html(
    brand_prompt: str,
    post_content: str,
    logo_b64: str,
) -> str:
    skill = FRONTEND_DESIGN_SKILL.read_text()
    system_prompt = f"""{skill}
You are generating a marketing graphic as a self-contained HTML file.

CRITICAL OUTPUT RULES:
- Output ONLY raw HTML — no markdown, no backticks, no explanation
- The graphic must be exactly 1200x627px (LinkedIn format)
- Everything must be self-contained — no external images
- Google Fonts via @import is allowed
- All content must be visible without scrolling
- Do not truncate — output the complete HTML file including closing tags
"""

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=8000,
        thinking={"type": "disabled"},
        system=system_prompt,
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

    html = response.content[0].text.strip()
    html = re.sub(r'^```(?:html)?\s*', '', html)
    html = re.sub(r'\s*```$', '', html)
    return html


def run(
    topic: str,
    brand_path: str,
    brain_path: str,
    logo_path: str,
    product_name: str = None,
    caption_path: str = None,
    html_path: str = None,
    brief_path: str = None,
) -> dict:
    """Full pipeline: topic → strategy brief → caption + HTML graphic."""
    caption_path = caption_path or str(DATA_DIR / "caption.txt")
    html_path = html_path or str(DATA_DIR / "output.html")
    brief_path = brief_path or str(DATA_DIR / "brief.json")

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
    post_content = brief_to_post_content(brief, logo_b64)

    with open(brief_path, "w") as f:
        json.dump(brief, f, indent=2)
    with open(caption_path, "w") as f:
        f.write(caption)

    html = generate_graphic_html(brand_prompt, post_content, logo_b64)
    with open(html_path, "w") as f:
        f.write(html)

    return {
        "brief": brief,
        "caption": caption,
        "post_content": post_content,
        "html": html,
        "caption_path": caption_path,
        "html_path": html_path,
        "brief_path": brief_path,
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
