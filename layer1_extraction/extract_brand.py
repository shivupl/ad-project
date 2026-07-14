import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anthropic
import requests
import json
import os
import re
from urllib.parse import urljoin
from dotenv import load_dotenv
from paths import DATA_DIR

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ─────────────────────────────────────────────
# STEP 1: Scrape homepage HTML + CSS
# ─────────────────────────────────────────────

def scrape_css(url: str) -> dict:
    """Scrape raw HTML and CSS from homepage only."""
    print(f"Scraping CSS from {url}...")

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        html = response.text

        css_content = ""

        # Inline style blocks
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)
        css_content += "\n".join(style_blocks)

        # Linked stylesheets — grab up to 8 to maximize chance of hitting theme CSS
        stylesheet_urls = re.findall(r'<link[^>]+href=["\']([^"\']+\.css[^"\']*)["\']', html)
        for css_url in stylesheet_urls[:8]:
            try:
                full_url = urljoin(url, css_url)
                css_resp = requests.get(full_url, headers=headers, timeout=8)
                css_content += "\n" + css_resp.text[:15000]
            except:
                pass

        return {
            "html": html[:20000],
            "css": css_content[:30000],
            "url": url
        }

    except Exception as e:
        print(f"Scrape error: {e}")
        return {"html": "", "css": "", "url": url}


# ─────────────────────────────────────────────
# STEP 2: Extract brand identity via Claude
# ─────────────────────────────────────────────

def extract_brand(scraped: dict) -> dict:
    """Extract visual brand identity and personality from HTML/CSS."""
    print("Extracting brand identity...")

    prompt = f"""
You are a brand analyst extracting visual identity and brand personality from a website.

Website URL: {scraped['url']}

HTML:
{scraped['html']}

CSS:
{scraped['css']}

Return ONLY a valid JSON object with this exact nested structure, no explanation, no markdown:

{{
  "company_name": "full company name",
  "website": "root domain URL",
  "visual_identity": {{
    "primary_color": "#hexcode",
    "secondary_color": "#hexcode",
    "accent_color": "#hexcode",
    "background_color": "#hexcode",
    "text_primary_color": "#hexcode",
    "fonts": {{
      "display": "headline font name or null",
      "body": "body font name or null",
      "google_fonts_url": "full Google Fonts @import URL or null"
    }},
    "logo_url": "absolute URL to logo image or null",
    "logo_path": null
  }},
  "brand_personality": {{
    "industry": "industry/sector in 3-5 words",
    "tone": ["adjective1", "adjective2", "adjective3"],
    "target_audience": ["audience segment 1", "audience segment 2"]
  }},
  "marketing_profile": {{
    "business_model": "b2b | d2c_consumer | prosumer_creative | mixed",
    "persuasion_mode": "rational | emotional | mixed",
    "evidence_types": ["2-5 items, most prominent first, from: metrics, case_studies, social_proof, credentials, price_value, transformation, lifestyle, aspiration, convenience"],
    "content_density": "minimal | balanced | dense",
    "cta_style": "book_demo | start_trial | shop_now | subscribe | learn_more",
    "example_ctas": ["verbatim CTA button texts from the homepage, up to 3"],
    "reasoning": "one sentence citing the homepage signals behind this classification"
  }}
}}

Rules:
- Colors: extract from CSS only — look for :root variables, body, h1, .btn, a, background-color
- Ignore WordPress admin colors: #f76a0c, #0693e3, #32373c, #1d2327 — these are NOT brand colors
- Fonts: look for @import url(https://fonts.googleapis.com/...) lines in CSS
- Tone: 2-4 adjectives describing how the brand communicates
- Target audience: 2-3 short descriptors of who they sell to (e.g. "enterprise lenders", "fintech startups")
- Industry: short description of what space they operate in
- marketing_profile: classify how this brand actually markets, from observable homepage signals:
  - "book a demo" / "talk to sales" / "request a quote", pricing hidden behind contact → business_model "b2b", cta_style "book_demo"
  - "shop now" / "add to cart" / visible consumer prices / product photography → "d2c_consumer", cta_style "shop_now"
  - self-serve "start free" / "sign up" aimed at individual creators or users → "prosumer_creative" or "mixed"
  - persuasion_mode: metric-led copy (numbers, ROI, accuracy claims) → "rational"; feeling-led copy (identity, transformation, convenience, second-person "you") → "emotional"; both prominent → "mixed"
  - evidence_types: what the homepage actually leans on to convince (stats vs testimonials vs price vs badges vs lifestyle imagery vs aspiration)
  - content_density: text/feature/data-heavy homepage → "dense"; imagery-led with sparse copy → "minimal"; else "balanced"
  - example_ctas: copy the literal button/link texts, do not paraphrase
- If a value cannot be found return null
- Return ONLY the JSON, nothing else
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'^```\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return {}


# ─────────────────────────────────────────────
# STEP 3: Build and save brand JSON
# ─────────────────────────────────────────────

def build_brand(url: str, logo_path: str = None) -> dict:
    """
    Pipeline: URL → scrape CSS → extract brand → save brand JSON.
    Pass logo_path to set local logo file.
    """

    scraped = scrape_css(url)
    brand   = extract_brand(scraped)

    if not brand:
        print("Brand extraction failed")
        return {}

    # Inject logo_path into nested structure
    if brand.get("visual_identity"):
        brand["visual_identity"]["logo_path"] = logo_path or None

    company_slug = brand.get("company_name", "company").lower().replace(" ", "_").replace(".", "").replace("/", "")
    output_path  = DATA_DIR / f"brand_{company_slug}.json"

    with open(output_path, "w") as f:
        json.dump(brand, f, indent=2)

    print(f"\nBrand saved → {output_path}")
    print(json.dumps(brand, indent=2))

    return brand


def marketing_profile_to_context(brand: dict) -> str:
    """Convert the marketing_profile block into a context string for the
    strategy agent. Returns "" when the brand JSON has no profile (legacy files)."""
    mp = brand.get("marketing_profile") or {}
    if not mp:
        return ""

    evidence_str = ", ".join(mp.get("evidence_types") or []) or "unknown"
    ctas_str = ", ".join(f'"{c}"' for c in (mp.get("example_ctas") or [])) or "none captured"

    return f"""MARKETING PROFILE:
- Business model: {mp.get('business_model') or 'unknown'}
- Persuasion mode: {mp.get('persuasion_mode') or 'unknown'}
- Evidence this brand leans on (most prominent first): {evidence_str}
- Content density: {mp.get('content_density') or 'unknown'}
- CTA style: {mp.get('cta_style') or 'unknown'} (their own CTAs: {ctas_str})"""


def _creative_direction(mp: dict) -> str:
    """Deterministic creative-direction block for the graphic generator,
    derived from the marketing profile. No LLM call."""
    mode = mp.get("persuasion_mode")
    density = mp.get("content_density")
    cta_style = mp.get("cta_style")
    example_ctas = ", ".join(f'"{c}"' for c in (mp.get("example_ctas") or []))

    if mode == "emotional" or density == "minimal":
        direction = """One dominant emotional idea. Drastically limit copy — every extra word weakens it.
            Generous whitespace. NO dashboard aesthetics: no grid backgrounds, no stacked stat
            panels, no data-tile layouts. At most ONE number on the entire canvas. Warm, human,
            imagery-like treatment over technical precision."""
    elif mode == "rational" and density == "dense":
        direction = """Data-forward composition is appropriate here: a stat hero, supporting metric
            chips, precise technical feel. Confidence through specificity."""
    else:
        direction = """One clear hero idea with at most 2 supporting proof elements. Balanced —
            neither a data dashboard nor a bare poster."""

    cta_line = ""
    if cta_style:
        register = "consumer, low-friction" if cta_style in ("shop_now", "subscribe", "start_trial") else "professional, considered"
        cta_line = f"\n            CTA register: {register} (matches their own CTAs: {example_ctas or cta_style})"

    return f"""
            CREATIVE DIRECTION — this overrides default styling instincts:
            {direction}{cta_line}
            """


#Convert brand JSON into brand guidelines prompt
def brand_to_prompt(brand: dict) -> str:
    """Convert brand JSON into brand guidelines string for Layer 4."""

    vi = brand.get("visual_identity", {})
    bp = brand.get("brand_personality", {})
    fonts = vi.get("fonts", {})

    tone_str     = ", ".join(bp.get("tone", [])) or "professional"
    audience_str = ", ".join(bp.get("target_audience", [])) or "business professionals"

    mp = brand.get("marketing_profile") or {}
    creative_direction = _creative_direction(mp) if mp else ""

    return f"""
            BRAND GUIDELINES — follow exactly:
            - Company: {brand.get('company_name', '')}
            - Website: {brand.get('website', '')}
            - Industry: {bp.get('industry', '')}
            - Tone: {tone_str}
            - Target audience: {audience_str}

            COLORS — use these exact hex values:
            - Primary: {vi.get('primary_color', '#000000')}
            - Secondary: {vi.get('secondary_color', '#333333')}
            - Accent: {vi.get('accent_color', '#0066FF')}
            - Background: {vi.get('background_color', '#FFFFFF')}
            - Text primary: {vi.get('text_primary_color', '#000000')}

            FONTS:
            - Display font: {fonts.get('display') or 'choose a distinctive Google Font'}
            - Body font: {fonts.get('body') or 'choose a clean readable Google Font'}
            - Google Fonts URL: {fonts.get('google_fonts_url') or 'choose appropriate Google Fonts'}

            LOGO: embedded in the image above — place top left, max height 36px, embed as base64 data URI
{creative_direction}"""


# RUN
if __name__ == "__main__":
    import sys

    url       = sys.argv[1] if len(sys.argv) > 1 else input("Enter website URL: ").strip()
    logo_path = sys.argv[2] if len(sys.argv) > 2 else None

    brand = build_brand(url, logo_path)

    if brand:
        print("\n--- Brand prompt preview ---")
        print(brand_to_prompt(brand))