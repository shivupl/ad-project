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

_FONT_CDN_HOSTS = (
    "fonts.googleapis.com", "fonts.bunny.net", "use.typekit.net",
    "fonts.cdnfonts.com", "cloud.typography.com", "fast.fonts.net",
)

_GENERIC_FONT_TOKENS = {
    "sans-serif", "serif", "monospace", "cursive", "fantasy",
    "system-ui", "-apple-system", "blinkmacsystemfont",
    "ui-sans-serif", "ui-serif", "ui-monospace",
    "inherit", "initial", "unset",
}

_ICON_FONT_HINTS = ("awesome", "icon", "glyph", "material symbols", "material icons", "dashicons", "eicons")


def _collect_font_evidence(html: str, css: str) -> str:
    """Pull every font signal out of the FULL html/css before truncation can
    eat it: font CDN links, @font-face names, font-family declarations."""
    evidence = []

    # Font CDN links — in HTML <link> tags and CSS @imports
    hrefs = re.findall(r'<link[^>]+href=["\']([^"\']+)["\']', html)
    hrefs += re.findall(r'@import\s+(?:url\()?\s*["\']?([^"\')\s;]+)', css)
    cdn_links = [h for h in hrefs if any(host in h for host in _FONT_CDN_HOSTS)]
    for link in list(dict.fromkeys(cdn_links))[:5]:
        evidence.append(f"Font CDN link: {link}")

    # @font-face family names (self-hosted fonts)
    faces = re.findall(r'@font-face\s*\{[^}]*?font-family\s*:\s*["\']?([^;"\'}]+)', css, re.IGNORECASE)
    face_names = [n.strip() for n in faces if n.strip()]
    for name in list(dict.fromkeys(face_names))[:8]:
        evidence.append(f"@font-face family: {name}")

    # font-family declarations — first (primary) family only, generic stacks dropped
    decls = re.findall(r'font-family\s*:\s*([^;}]+)', css, re.IGNORECASE)
    primaries = []
    for d in decls:
        first = d.split(",")[0].strip().strip("'\"").strip()
        if not first or first.lower() in _GENERIC_FONT_TOKENS or first.lower().startswith("var("):
            continue
        primaries.append(first)
    for name in list(dict.fromkeys(primaries))[:10]:
        evidence.append(f"font-family declaration: {name}")

    return "\n".join(evidence)


def _css_from_html(html: str, url: str, headers: dict) -> str:
    """Inline <style> blocks plus fetched linked stylesheets from an HTML page."""
    css_content = ""

    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)
    css_content += "\n".join(style_blocks)

    # Any rel="stylesheet" link, not just *.css URLs
    # (Google Fonts links look like fonts.googleapis.com/css2?family=... with no .css)
    stylesheet_urls = []
    for tag in re.findall(r'<link[^>]*>', html):
        if "stylesheet" not in tag.lower():
            continue
        href = re.search(r'href=["\']([^"\']+)["\']', tag)
        if href:
            stylesheet_urls.append(href.group(1))

    for css_url in stylesheet_urls[:8]:
        try:
            full_url = urljoin(url, css_url)
            css_resp = requests.get(full_url, headers=headers, timeout=8)
            css_content += "\n" + css_resp.text[:15000]
        except:
            pass

    return css_content


def _rendered_html_fallback(url: str) -> str:
    """Fetch the JS-rendered page via Firecrawl, for sites that serve an empty
    shell or a bot challenge to plain requests (Adobe, Cloudflare-protected
    sites). Returns "" if unavailable so the caller degrades gracefully."""
    try:
        from firecrawl import FirecrawlApp
        fc = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
        doc = fc.scrape(url, formats=["rawHtml"])
        return doc.raw_html or ""
    except Exception as e:
        print(f"Rendered-scrape fallback failed: {e}")
        return ""


def scrape_css(url: str) -> dict:
    """Scrape raw HTML and CSS from homepage only."""
    print(f"Scraping CSS from {url}...")

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    html = ""
    try:
        response = requests.get(url, headers=headers, timeout=15)
        html = response.text
    except Exception as e:
        print(f"Scrape error: {e}")

    css_content = _css_from_html(html, url, headers) if html else ""
    font_evidence = _collect_font_evidence(html, css_content)

    # JS-heavy or bot-blocked sites give plain requests a shell/challenge page —
    # thin CSS or zero font signals both smell like one (a real page virtually
    # always has font-family declarations). Retry with a rendered scrape.
    if len(css_content.strip()) < 2500 or not font_evidence:
        print("Thin CSS / no font signals from plain scrape — trying rendered scrape via Firecrawl...")
        rendered = _rendered_html_fallback(url)
        if rendered:
            html = rendered
            css_content = _css_from_html(html, url, headers)
            font_evidence = _collect_font_evidence(html, css_content)

    return {
        "html": html[:20000],
        "css": css_content[:30000],
        "font_evidence": font_evidence,
        "url": url
    }


# ─────────────────────────────────────────────
# STEP 2: Extract brand identity via Claude
# ─────────────────────────────────────────────

def extract_brand(scraped: dict) -> dict:
    """Extract visual brand identity and personality from HTML/CSS."""
    print("Extracting brand identity...")

    prompt = f"""
You are a brand analyst extracting visual identity and brand personality from a website.

Website URL: {scraped['url']}

FONT EVIDENCE (every font signal found on the full page, collected before truncation):
{scraped.get('font_evidence') or 'none found'}

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
- Fonts: the FONT EVIDENCE section is your primary source — do not return null if it has usable signals:
  - Font CDN links carry family names in the URL itself (e.g. css2?family=Manrope:wght@400;700 → "Manrope")
  - @font-face families are self-hosted brand fonts — clean framework-mangled names ("__Inter_a1b2c3" → "Inter", "SuisseIntl-Regular" → "Suisse Intl")
  - font-family declarations show what's actually used; the most repeated non-generic family is usually the body font, a distinct one used sparingly is usually the display font
  - Ignore icon fonts (Font Awesome, Material Icons, dashicons) — they are not brand typography
  - If display and body appear to be the same family, return it for both
  - Only return null if the evidence contains nothing but generic system stacks
  - google_fonts_url: the full Google Fonts URL if one appears in the evidence, else null
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
        model="claude-sonnet-5",
        max_tokens=2000,
        thinking={"type": "disabled"},
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