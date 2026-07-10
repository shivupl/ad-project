import anthropic
import json
import os
import re
from dotenv import load_dotenv
from firecrawl import FirecrawlApp

load_dotenv()

client   = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
firecrawl = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))


# ─────────────────────────────────────────────
# STEP 1: Crawl full website via Firecrawl
# ─────────────────────────────────────────────

def crawl_website(url: str, max_pages: int = 20) -> dict:
    """Crawl full site and return clean markdown per page."""
    print(f"Crawling {url} (up to {max_pages} pages)...")

    try:
        result = firecrawl.crawl(
            url,
            limit=max_pages,
            formats=["markdown"],
            exclude_tags=["nav", "footer", "header", "script", "style"],
        )

        pages = []
        for page in result.data or []:
            meta = page.metadata_dict
            pages.append({
                "url":     meta.get("source_url") or meta.get("url") or "",
                "title":   meta.get("title") or "",
                "content": (page.markdown or "")[:8000],
            })

        print(f"Crawled {len(pages)} pages")
        return {"pages": pages, "url": url}

    except Exception as e:
        print(f"Crawl error: {e}")
        return {"pages": [], "url": url}


# ─────────────────────────────────────────────
# STEP 2: Extract company knowledge via Claude
# ─────────────────────────────────────────────

def extract_brain(crawled: dict) -> dict:
    """Extract structured company knowledge from crawled content."""
    print("Extracting company knowledge...")

    all_content = ""
    for page in crawled["pages"]:
        all_content += f"\n\n--- PAGE: {page['url']} ---\n{page['content']}"

    prompt = f"""
You are a marketing knowledge analyst. Extract structured company knowledge for use by a marketing AI agent.

Website: {crawled['url']}

FULL SITE CONTENT:
{all_content[:30000]}

Return ONLY a valid JSON object, no explanation, no markdown, no backticks:

{{
  "company_name": "full company name",
  "tagline": "main tagline or value proposition",
  "industry": "industry/sector",
  "industry_slug": "fintech | b2b_saas | healthcare | devtools | ecommerce | other",
  "target_audience": "specific description of who they sell to",
  "icp": "ideal customer profile — most specific description of best customer",
  "tone": "2-4 adjectives describing brand tone",

  "products": [
    {{
      "name": "product name",
      "description": "what it does in one sentence",
      "key_features": ["up to 5 features"],
      "use_cases": ["up to 3 use cases"],
      "metrics": ["specific stats for this product only"]
    }}
  ],

  "value_propositions": ["up to 5 company-wide value props"],
  "key_metrics": ["up to 8 specific stats with numbers"],
  "customer_quotes": ["verbatim quotes with full attribution"],
  "notable_clients": ["company names"],
  "case_study_results": ["specific outcomes with numbers"],
  "differentiators": ["what makes them different from competitors"],
  "key_messages": ["important messaging points"],
  "words_they_use": ["characteristic vocabulary and phrases"],
  "awards_certifications": ["awards, certifications, regulatory approvals"]
}}

Rules:
- Products must be separated — never mix metrics from different products
- Customer quotes must be verbatim with speaker name and title
- Metrics must include exact numbers and context
- Only extract what is explicitly stated — never invent or infer
- Empty fields use null or []
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
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
        print(f"Raw: {raw[:300]}")
        return {}


# ─────────────────────────────────────────────
# STEP 3: Build and save brain JSON
# ─────────────────────────────────────────────

def build_brain(url: str, max_pages: int = 20) -> dict:
    """
    Pipeline: URL → crawl full site → extract knowledge → save brain JSON.
    """

    crawled = crawl_website(url, max_pages)
    brain   = extract_brain(crawled)

    if not brain:
        print("Brain extraction failed")
        return {}

    company_slug = brain.get("company_name", "company").lower().replace(" ", "_").replace(".", "").replace("/", "")
    output_path  = f"brain_{company_slug}.json"

    with open(output_path, "w") as f:
        json.dump(brain, f, indent=2)

    print(f"\nBrain saved → {output_path}")
    print(json.dumps(brain, indent=2))

    return brain


# ─────────────────────────────────────────────
# STEP 4: Format brain context for strategy agent
# ─────────────────────────────────────────────

def brain_to_context(brain: dict, product_name: str = None) -> str:
    """Convert brain JSON into context string for Layer 2 strategy agent."""

    nl = "\n"
    metrics = brain.get("key_metrics", [])
    product_section = ""

    if product_name and brain.get("products"):
        for p in brain["products"]:
            if p["name"].lower() == product_name.lower():
                metrics = p.get("metrics", metrics)
                product_section = f"""
PRODUCT FOCUS: {p['name']}
- Description: {p.get('description', '')}
- Key features:
{nl.join([f"  · {f}" for f in p.get('key_features', [])])}
- Use cases:
{nl.join([f"  · {u}" for u in p.get('use_cases', [])])}
"""
                break

    return f"""
COMPANY KNOWLEDGE:
- Company: {brain.get('company_name', '')}
- Tagline: {brain.get('tagline', '')}
- Industry: {brain.get('industry', '')}
- Tone: {brain.get('tone', '')}
- Target audience: {brain.get('target_audience', '')}
- ICP: {brain.get('icp', '')}
{product_section}
KEY METRICS:
{nl.join([f"  - {m}" for m in metrics]) or "  - None"}

VALUE PROPOSITIONS:
{nl.join([f"  - {v}" for v in brain.get("value_propositions", [])]) or "  - None"}

CUSTOMER QUOTES (use verbatim):
{nl.join([f"  - {q}" for q in brain.get("customer_quotes", [])[:3]]) or "  - None"}

DIFFERENTIATORS:
{nl.join([f"  - {d}" for d in brain.get("differentiators", [])]) or "  - None"}

NOTABLE CLIENTS: {", ".join(brain.get("notable_clients", [])[:10]) or "None"}

KEY MESSAGES:
{nl.join([f"  - {m}" for m in brain.get("key_messages", [])]) or "  - None"}

BRAND VOCABULARY:
{", ".join(brain.get("words_they_use", [])) or "None"}

AWARDS & CERTIFICATIONS:
{nl.join([f"  - {a}" for a in brain.get("awards_certifications", [])]) or "  - None"}
"""


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else input("Enter website URL: ").strip()

    brain = build_brain(url)

    if brain and brain.get("products"):
        first = brain["products"][0]["name"]
        print(f"\n--- Brain context preview ({first}) ---")
        print(brain_to_context(brain, product_name=first))
