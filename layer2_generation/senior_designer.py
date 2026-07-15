import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anthropic
import base64
import os
import re
from dotenv import load_dotenv

from paths import SENIOR_DESIGNER_SKILL

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _approved_copy(brief: dict) -> str:
    """The exhaustive copy list the senior is allowed to keep on the canvas."""
    graphic = brief.get("graphic", {})
    lines = []
    for field in ("headline", "stat_hero", "contrast_line", "subtext", "cta"):
        value = graphic.get(field)
        if value:
            lines.append(f'- {field}: "{value}"')
    for m in (graphic.get("metrics") or [])[:2]:
        lines.append(f'- metric: "{m}"')
    return "\n".join(lines)


def review_and_enhance(html: str, png_path: str, brief: dict, brand_prompt: str) -> tuple:
    """Senior designer pass: sees the rendered screenshot + the HTML source,
    fixes defects, critiques the craft, returns an enhanced version of the
    same design. Returns (enhanced_html, critique) — or (html, None) if the
    review fails, so the pipeline degrades to the junior's version."""
    print("Senior designer review...")

    try:
        png_b64 = base64.standard_b64encode(Path(png_path).read_bytes()).decode()

        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=16000,
            thinking={"type": "disabled"},
            system=SENIOR_DESIGNER_SKILL.read_text(),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": png_b64}},
                    {"type": "text", "text": f"""The image above is the rendered screenshot of the junior designer's graphic.

BRAND GUIDELINES:
{brand_prompt}

APPROVED COPY (exhaustive — no other text is allowed on the canvas):
{_approved_copy(brief)}

HTML SOURCE:
{html}

Review and return the enhanced HTML per your output format."""},
                ],
            }],
        )

        if response.stop_reason == "max_tokens":
            print("Senior review hit max_tokens — keeping junior version")
            return html, None

        raw = response.content[0].text.strip()
        raw = re.sub(r'^```(?:html)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        critique = None
        match = re.match(r'\s*<!--\s*REVIEW:\s*(.*?)\s*-->\s*', raw, re.DOTALL)
        if match:
            critique = match.group(1).strip()
            raw = raw[match.end():].strip()

        if not raw.lstrip().lower().startswith(("<!doctype", "<html")):
            print("Senior review returned malformed HTML — keeping junior version")
            return html, critique

        return raw, critique

    except Exception as e:
        print(f"Senior review failed, keeping junior version: {e}")
        return html, None
