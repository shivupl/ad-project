import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anthropic
import json
import os
import re
from datetime import date
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from paths import DATA_DIR

load_dotenv()

client   = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
firecrawl = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))


# ─────────────────────────────────────────────
# STEP 1: Discover → filter → rank → fetch only the relevant pages
# ─────────────────────────────────────────────

_JUNK_PATH_SEGMENTS = (
    "/login", "/signup", "/sign-up", "/sign-in", "/cart", "/checkout",
    "/account", "/privacy", "/terms", "/cookie", "/legal",
)
_ASSET_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".css", ".js",
    ".xml", ".ico", ".woff", ".woff2",
)


def discover_pages(url: str, limit: int = 100) -> list[dict]:
    """Cheap URL discovery via firecrawl.map() — no content fetch.
    Returns [{'url', 'title', 'description'}, ...]; [] on error."""
    print(f"Discovering pages on {url}...")

    try:
        result = firecrawl.map(url, limit=limit)
        links = [
            {"url": link.url, "title": link.title or "", "description": link.description or ""}
            for link in (result.links or [])
        ]
        print(f"Discovered {len(links)} candidate pages")
        return links

    except Exception as e:
        print(f"Discovery error: {e}")
        return []


def filter_candidate_pages(links: list[dict]) -> list[dict]:
    """Pure heuristic, no network/LLM: drop obviously irrelevant pages
    (auth/account/legal, pagination, non-HTML assets) and exact duplicates."""
    seen = set()
    filtered = []

    for link in links:
        page_url = link.get("url") or ""
        if not page_url or page_url in seen:
            continue
        lower = page_url.lower()

        if any(seg in lower for seg in _JUNK_PATH_SEGMENTS):
            continue
        if any(lower.endswith(ext) for ext in _ASSET_EXTENSIONS):
            continue
        if "?page=" in lower or re.search(r"/page/\d+", lower):
            continue

        seen.add(page_url)
        filtered.append(link)

    return filtered


def _claude_json_list(prompt: str, model: str = "claude-haiku-4-5-20251001", max_tokens: int = 1000):
    """One cheap Claude call expecting a JSON array response. Returns the list,
    or None on any API/parse failure — the caller decides the fallback."""
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'^```\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        result = json.loads(raw)
        return result if isinstance(result, list) and result else None

    except Exception as e:
        print(f"Claude JSON-list call failed: {e}")
        return None


def rank_relevant_pages(candidates: list[dict], url: str, max_pages: int) -> list[str]:
    """One cheap Claude call ranks candidate pages by title/description and
    returns the URLs most useful for a marketing knowledge base. Falls back
    to heuristic order (candidates[:max_pages]) on any API/parse failure —
    never hard-fails the pipeline over a ranking hiccup."""
    fallback = [c["url"] for c in candidates[:max_pages]]
    if not candidates:
        return fallback

    listing = "\n".join(
        f"- {c['url']} | title: {c['title']} | description: {c['description']}"
        for c in candidates
    )

    prompt = f"""
Website: {url}

Below is a list of candidate pages discovered on this site (url | title | description).
Select the {max_pages} pages MOST useful for building a marketing knowledge base —
prioritize: product/feature pages, pricing, about/company, case studies, customer
stories/testimonials, and any page with concrete metrics or differentiators.
Deprioritize: generic blog listing pages, careers, contact, individual old blog posts
unless clearly a cornerstone/flagship piece.

CANDIDATE PAGES:
{listing}

Return ONLY a JSON array of up to {max_pages} URLs, most relevant first, no explanation:
["url1", "url2", ...]
"""

    selected = _claude_json_list(prompt)
    return selected[:max_pages] if selected else fallback


def fetch_pages(urls: list[str], url: str) -> dict:
    """Fetch full content for pre-selected URLs via firecrawl.batch_scrape().
    Falls back to a single homepage scrape() if batch_scrape fails."""
    print(f"Fetching {len(urls)} selected pages...")

    try:
        result = firecrawl.batch_scrape(
            urls,
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

        print(f"Fetched {len(pages)} pages")
        return {"pages": pages, "url": url}

    except Exception as e:
        print(f"Batch fetch error, falling back to homepage only: {e}")
        try:
            page = firecrawl.scrape(url, formats=["markdown"])
            meta = page.metadata_dict
            return {
                "pages": [{
                    "url":     meta.get("source_url") or meta.get("url") or url,
                    "title":   meta.get("title") or "",
                    "content": (page.markdown or "")[:8000],
                }],
                "url": url,
            }
        except Exception as e2:
            print(f"Homepage fallback also failed: {e2}")
            return {"pages": [], "url": url}


def crawl_website(url: str, max_pages: int = 20) -> dict:
    """Pipeline: discover candidate pages cheaply → filter obvious junk →
    rank the rest for relevance → fetch full content only for the top pages.
    Same signature/return shape as before, so build_brain() needs no changes."""
    links = discover_pages(url)
    if not links:
        return fetch_pages([url], url)

    candidates = filter_candidate_pages(links) or links
    selected = rank_relevant_pages(candidates, url, max_pages)
    return fetch_pages(selected, url)


# ─────────────────────────────────────────────
# STEP 2: Extract company knowledge via Claude
# ─────────────────────────────────────────────

# Shared by website extraction (below) and document enrichment (enrich_brain.py)
# so the two paths can never drift apart on schema.
BRAIN_SCHEMA_PROMPT = """
Return ONLY a valid JSON object, no explanation, no markdown, no backticks:

{
  "company_name": "full company name",
  "tagline": "main tagline or value proposition",
  "industry": "industry/sector",
  "industry_slug": "fintech | b2b_saas | healthcare | devtools | ecommerce | other",
  "target_audience": "specific description of who they sell to",
  "icp": "ideal customer profile — most specific description of best customer",
  "tone": "2-4 adjectives describing brand tone",

  "products": [
    {
      "name": "product name",
      "description": "1-3 sentences capturing what it does, direct from source content",
      "key_features": ["up to 8 features"],
      "use_cases": ["up to 5 use cases"],
      "metrics": ["specific stats for this product only"],
      "audience_type": "b2b | consumer | prosumer | null"
    }
  ],

  "value_propositions": ["up to 8 company-wide value props"],
  "key_metrics": ["up to 15 specific stats with numbers"],
  "offers_pricing": ["price points, free trials, guarantees, discounts, membership terms"],
  "customer_pain_points": ["problems and feelings the brand explicitly addresses"],
  "brand_promises": ["transformation or outcome statements the brand makes"],
  "customer_quotes": ["verbatim quotes with full attribution"],
  "notable_clients": ["company names"],
  "case_study_results": ["specific outcomes with numbers"],
  "differentiators": ["what makes them different from competitors"],
  "key_messages": ["important messaging points"],
  "words_they_use": ["characteristic vocabulary and phrases"],
  "awards_certifications": ["awards, certifications, regulatory approvals"]
}

Rules:
- Products must be separated — never mix metrics from different products
- audience_type per product: who the product is framed for — "b2b" (companies,
  teams, enterprise buyers), "consumer" (individuals buying for themselves),
  "prosumer" (individual professionals/creators), or null if unclear
- Customer quotes must be verbatim with speaker name and title
- Metrics must include exact numbers and context
- Pricing belongs in offers_pricing, NOT in key_metrics — key_metrics is for
  performance/outcome stats, offers_pricing is for what things cost and deal terms
- customer_pain_points: only problems/feelings the content explicitly names or
  clearly addresses (e.g. "no waiting rooms" implies the waiting-room pain) —
  never invent psychology
- brand_promises: outcome statements made directly to the customer ("Lose up to
  25% body weight", "Results in 3-6 months", "100% online")
- Only extract what is explicitly stated — never invent or infer
- For customer_quotes, notable_clients, case_study_results, differentiators, and
  key_messages: extract ALL clearly stated items found in the content, not just a
  sample — this is a knowledge base for many future posts, not a single summary,
  so completeness matters more than brevity here
- Empty fields use null or []
"""


def run_brain_extraction(content) -> dict:
    """One claude-sonnet-4-6 extraction call with retry-once-on-parse-failure.
    content: a plain string, or a list of content blocks (for document input)."""
    for attempt in range(2):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            messages=[{"role": "user", "content": content}]
        )

        if response.stop_reason == "max_tokens":
            print("Warning: extraction response hit max_tokens — output may be truncated/invalid JSON")

        raw = response.content[0].text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'^```\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"JSON parse error (attempt {attempt + 1}): {e}")
            print(f"Raw: {raw[:300]}")

    return {}


def extract_brain(crawled: dict) -> dict:
    """Extract structured company knowledge from crawled content."""
    print("Extracting company knowledge...")

    all_content = ""
    for page in crawled["pages"]:
        all_content += f"\n\n--- PAGE: {page['url']} ---\n{page['content']}"

    # Content is already relevance-curated by crawl_website() upstream, so this is
    # a backstop cap (not the primary control): 20 pages x 8000-char cap = 160000
    # worst case, 60000 covers a generous handful of full curated pages.
    prompt = f"""
You are a marketing knowledge analyst. Extract structured company knowledge for use by a marketing AI agent.

Website: {crawled['url']}

FULL SITE CONTENT:
{all_content[:60000]}
{BRAIN_SCHEMA_PROMPT}"""

    return run_brain_extraction(prompt)


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

    brain["sources"] = [{"type": "website", "ref": url, "added": date.today().isoformat()}]

    company_slug = brain.get("company_name", "company").lower().replace(" ", "_").replace(".", "").replace("/", "")
    output_path  = DATA_DIR / f"brain_{company_slug}.json"

    with open(output_path, "w") as f:
        json.dump(brain, f, indent=2)

    print(f"\nBrain saved → {output_path}")
    print(json.dumps(brain, indent=2))

    return brain


# ─────────────────────────────────────────────
# STEP 4: Format brain context for strategy agent
# ─────────────────────────────────────────────

def select_by_relevance(items: list[str], topic: str, purpose: str, max_items: int) -> list[str]:
    """If items already fits within max_items, return as-is (no API call needed).
    Otherwise, if topic is given, one cheap Claude call picks the max_items most
    relevant to topic. Falls back to items[:max_items] if topic is None, the
    pool is empty, or the call fails."""
    if len(items) <= max_items:
        return items

    fallback = items[:max_items]
    if not topic:
        return fallback

    listing = "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))
    prompt = f"""
A marketing post is being written about this topic: "{topic}"

Below is a numbered pool of {purpose} available for this company. Select the {max_items} MOST
relevant to the topic above — the ones that would make the strongest, most specific
supporting evidence for a post on this exact topic.

POOL:
{listing}

Return ONLY a JSON array of up to {max_items} item NUMBERS (integers) from the list above,
most relevant first, no explanation. Return numbers only, never the item text itself
(some items contain quote marks that break JSON if copied directly):
[3, 7, 1]
"""

    selected_numbers = _claude_json_list(prompt)
    if not selected_numbers:
        return fallback

    result = []
    for n in selected_numbers:
        try:
            idx = int(n)
        except (TypeError, ValueError):
            continue
        if 1 <= idx <= len(items):
            result.append(items[idx - 1])

    return result[:max_items] if result else fallback


def brain_to_context(brain: dict, product_name: str = None, topic: str = None) -> str:
    """Convert brain JSON into context string for Layer 2 strategy agent.
    When topic is given, quotes/metrics/case studies are selected for relevance
    to that specific post rather than always showing the same first few."""

    nl = "\n"
    metrics = brain.get("key_metrics", [])
    product_section = ""

    if product_name and brain.get("products"):
        for p in brain["products"]:
            if p["name"].lower() == product_name.lower():
                metrics = p.get("metrics", metrics)
                audience_line = f"\n- Audience type: {p['audience_type']}" if p.get("audience_type") else ""
                product_section = f"""
PRODUCT FOCUS: {p['name']}
- Description: {p.get('description', '')}{audience_line}
- Key features:
{nl.join([f"  · {f}" for f in p.get('key_features', [])])}
- Use cases:
{nl.join([f"  · {u}" for u in p.get('use_cases', [])])}
"""
                break

    metrics = select_by_relevance(metrics, topic, "company/product metrics and stats", max_items=10)
    quotes = select_by_relevance(brain.get("customer_quotes", []), topic, "customer quotes", max_items=4)
    case_studies = select_by_relevance(brain.get("case_study_results", []), topic, "case study results", max_items=4)

    # Consumer-shaped sections: only included when the brain actually has them,
    # so legacy B2B brains don't get noise sections full of "None".
    offers = select_by_relevance(brain.get("offers_pricing") or [], topic, "offers, pricing and promotions", max_items=6)
    pain_points = select_by_relevance(brain.get("customer_pain_points") or [], topic, "customer pain points and emotional drivers", max_items=5)
    promises = select_by_relevance(brain.get("brand_promises") or [], topic, "transformation and outcome promises", max_items=5)

    consumer_sections = ""
    if offers:
        consumer_sections += f"""
OFFERS & PRICING:
{nl.join([f"  - {o}" for o in offers])}
"""
    if pain_points:
        consumer_sections += f"""
CUSTOMER PAIN POINTS (what the brand solves for people):
{nl.join([f"  - {p}" for p in pain_points])}
"""
    if promises:
        consumer_sections += f"""
BRAND PROMISES (outcomes stated to the customer):
{nl.join([f"  - {b}" for b in promises])}
"""

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
{consumer_sections}
CUSTOMER QUOTES (use verbatim):
{nl.join([f"  - {q}" for q in quotes]) or "  - None"}

CASE STUDY RESULTS:
{nl.join([f"  - {c}" for c in case_studies]) or "  - None"}

DIFFERENTIATORS:
{nl.join([f"  - {d}" for d in brain.get("differentiators", [])]) or "  - None"}

NOTABLE CLIENTS: {", ".join(brain.get("notable_clients", [])[:15]) or "None"}

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
