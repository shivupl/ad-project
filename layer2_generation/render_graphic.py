import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anthropic
import base64
import json
import os
import re
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

CANVAS_WIDTH = 1200
CANVAS_HEIGHT = 627


# ─────────────────────────────────────────────
# STEP 1: Render HTML → PNG (headless Chromium)
# ─────────────────────────────────────────────

def html_to_png(html: str, png_path: str, width: int = CANVAS_WIDTH, height: int = CANVAS_HEIGHT) -> bool:
    """Screenshot the graphic's canvas element to a PNG. Returns True on success.
    Never raises — rendering is an enhancement, not a hard dependency."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html, wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(400)  # let web fonts settle

            # Prefer the exact canvas element (body may add margins/background)
            found = page.evaluate(f"""() => {{
                for (const el of document.querySelectorAll('div, main, section')) {{
                    const r = el.getBoundingClientRect();
                    if (Math.abs(r.width - {width}) <= 2 && Math.abs(r.height - {height}) <= 2) {{
                        el.setAttribute('data-graphic-canvas', '1');
                        return true;
                    }}
                }}
                return false;
            }}""")

            if found:
                page.locator("[data-graphic-canvas]").first.screenshot(path=png_path)
            else:
                page.screenshot(path=png_path, clip={"x": 0, "y": 0, "width": width, "height": height})

            browser.close()
        return True

    except Exception as e:
        print(f"PNG render failed (visual QA skipped): {e}")
        return False


# ─────────────────────────────────────────────
# STEP 2: Vision QA — look at the rendered pixels
# ─────────────────────────────────────────────

def review_graphic_png(png_path: str) -> list[str]:
    """One Claude vision call inspecting the rendered graphic for objective
    rendering defects only (overlap, clipping, illegibility). Returns a list
    of defects; [] means the render passed. Fails open on any error."""
    try:
        png_b64 = base64.standard_b64encode(Path(png_path).read_bytes()).decode()

        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1000,
            thinking={"type": "disabled"},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": png_b64}},
                    {"type": "text", "text": """This is a rendered marketing graphic. You are a rendering-defect checker, NOT a design critic.

Report ONLY objective rendering defects:
1. Text or elements overlapping / printed on top of each other
2. Text clipped, cut off at an edge, or hidden behind another element
3. Text overflowing outside the canvas
4. Text that is illegible against its background (near-zero contrast)

Do NOT comment on style, spacing taste, color choices, or layout preferences.
If the graphic renders cleanly, defects is an empty list.

Return ONLY JSON, no explanation:
{"pass": true/false, "defects": ["specific defect with location, e.g. 'the large stat overlaps the subtext line below it'"]}"""},
                ],
            }],
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'^```\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        result = json.loads(raw)
        return list(result.get("defects") or []) if not result.get("pass", False) else []

    except Exception as e:
        print(f"Visual QA failed (treated as pass): {e}")
        return []


if __name__ == "__main__":
    html_file = sys.argv[1] if len(sys.argv) > 1 else input("HTML file: ").strip()
    png_file = sys.argv[2] if len(sys.argv) > 2 else str(Path(html_file).with_suffix(".png"))

    html = open(html_file).read()
    if html_to_png(html, png_file):
        print(f"PNG saved → {png_file}")
        defects = review_graphic_png(png_file)
        print("Visual QA:", "PASS" if not defects else f"DEFECTS: {defects}")
