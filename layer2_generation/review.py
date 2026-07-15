"""Everything that looks at the rendered graphic: screenshotting, the senior
designer review (fix + critique + enhance), the objective defect gate, and
surgical repair. The generator writes HTML blind — this module is its eyes."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import base64
import re

import llm
from paths import SENIOR_DESIGNER_SKILL

CANVAS_WIDTH = 1200
CANVAS_HEIGHT = 627


def _png_block(png_path: str) -> dict:
    data = base64.standard_b64encode(Path(png_path).read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}


# ─────────────────────────────────────────────
# Render HTML → PNG (headless Chromium)
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
# Senior designer review — fix + critique + enhance
# ─────────────────────────────────────────────

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
        content = [
            _png_block(png_path),
            {"type": "text", "text": f"""The image above is the rendered screenshot of the junior designer's graphic.

BRAND GUIDELINES:
{brand_prompt}

APPROVED COPY (exhaustive — no other text is allowed on the canvas):
{_approved_copy(brief)}

HTML SOURCE:
{html}

Review and return the enhanced HTML per your output format."""},
        ]

        raw = llm.complete(content, max_tokens=16000, system=SENIOR_DESIGNER_SKILL.read_text())

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


# ─────────────────────────────────────────────
# Objective defect gate + surgical repair
# ─────────────────────────────────────────────

def find_defects(png_path: str) -> list:
    """Vision inspection of the rendered graphic for objective rendering
    defects only (overlap, clipping, overflow, illegibility). Returns a list
    of defects; [] means the render passed. Fails open on any error."""
    try:
        content = [
            _png_block(png_path),
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
        ]

        result = llm.complete_json(content, max_tokens=1000, retries=1)
        if not isinstance(result, dict):
            return []
        return list(result.get("defects") or []) if not result.get("pass", False) else []

    except Exception as e:
        print(f"Visual QA failed (treated as pass): {e}")
        return []


def repair_html(html: str, png_path: str, defects: list) -> str:
    """Surgical repair: the model sees its own HTML alongside the rendered
    screenshot and the defect list, and fixes ONLY the defects while
    preserving the design and copy. Returns the corrected HTML — or the
    original unchanged if the call fails."""
    try:
        defects_str = "\n".join(f"- {d}" for d in defects)

        content = [
            _png_block(png_path),
            {"type": "text", "text": f"""The screenshot above is the rendered result of the HTML below. It has these rendering defects:
{defects_str}

Fix ONLY these defects with minimal changes — adjust font sizes, line heights, spacing, or element positions as needed. Do NOT redesign, do NOT change any copy, do NOT alter colors or fonts, and keep the logo <img> tag (with its src placeholder) exactly as it is.

Return ONLY the complete corrected HTML file, no markdown, no backticks, no explanation.

HTML:
{html}"""},
        ]

        fixed = llm.complete(content, max_tokens=16000)
        return fixed if fixed.lstrip().lower().startswith(("<!doctype", "<html")) else html

    except Exception as e:
        print(f"Repair call failed, keeping original HTML: {e}")
        return html


# ─────────────────────────────────────────────
# RUN — inspect any HTML file from the CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    html_file = sys.argv[1] if len(sys.argv) > 1 else input("HTML file: ").strip()
    png_file = sys.argv[2] if len(sys.argv) > 2 else str(Path(html_file).with_suffix(".png"))

    html = open(html_file).read()
    if html_to_png(html, png_file):
        print(f"PNG saved → {png_file}")
        defects = find_defects(png_file)
        print("Visual QA:", "PASS" if not defects else f"DEFECTS: {defects}")
