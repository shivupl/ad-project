import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import re
from datetime import date

import llm
from paths import DATA_DIR


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


def discover_pages(url: str, limit: int = 100) -> list:
    """Cheap URL discovery via firecrawl.map() — no content fetch.
    Returns [{'url', 'title', 'description'}, ...]; [] on error."""
    print(f"Discovering pages on {url}...")

    try:
        result = llm.firecrawl.map(url, limit=limit)
        links = [
            {"url": link.url, "title": link.title or "", "description": link.description or ""}
            for link in (result.links or [])
        ]
        print(f"Discovered {len(links)} candidate pages")
        return links

    except Exception as e:
        print(f"Discovery error: {e}")
        return []


def filter_candidate_pages(links: list) -> list:
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


def rank_relevant_pages(candidates: list, url: str, max_pages: int) -> list:
    """One cheap model call ranks candidate pages by title/description and
    returns the URLs most useful for a marketing knowledge base. Falls back
    to heuristic order (candidates[:max_pages]) on any failure."""
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

    selected = llm.complete_json(prompt, model=llm.MODEL_LIGHT, max_tokens=1000, retries=1)
    if isinstance(selected, list) and selected:
        return selected[:max_pages]
    return fallback


def fetch_pages(urls: list, url: str) -> dict:
    """Fetch full content for pre-selected URLs via firecrawl.batch_scrape().
    Falls back to a single homepage scrape() if batch_scrape fails."""
    print(f"Fetching {len(urls)} selected pages...")

    try:
        result = llm.firecrawl.batch_scrape(
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
            page = llm.firecrawl.scrape(url, formats=["markdown"])
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
    rank the rest for relevance → fetch full content only for the top pages."""
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
    """One extraction call against the brain schema. `content` is a plain
    string, or a list of content blocks (for document input)."""
    return llm.complete_json(content, max_tokens=8000) or {}


def extract_brain(crawled: dict) -> dict:
    """Extract structured company knowledge from crawled content."""
    print("Extracting company knowledge...")

    all_content = ""
    for page in crawled["pages"]:
        all_content += f"\n\n--- PAGE: {page['url']} ---\n{page['content']}"

    # Content is already relevance-curated by crawl_website() upstream, so this is
    # a backstop cap (not the primary control).
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
    """Pipeline: URL → crawl site → extract knowledge → save brain JSON."""
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
    return brain


# ─────────────────────────────────────────────
# STEP 4: Format brain context for the strategy agent
# ─────────────────────────────────────────────

# Per-pool caps for the strategy context: (brain field, cap)
_CONTEXT_POOLS = [
    ("key_metrics", 10),
    ("customer_quotes", 4),
    ("case_study_results", 4),
    ("offers_pricing", 6),
    ("customer_pain_points", 5),
    ("brand_promises", 5),
]


def _select_relevant(pools: dict, topic: str) -> dict:
    """Topic-aware selection across ALL context pools in ONE cheap model call
    (previously up to six separate calls per post). Each pool is a numbered
    list; the model returns item numbers per pool — numbers, not text, because
    quotes contain characters that break JSON when echoed back.
    Falls back to first-N per pool if topic is missing or the call fails."""
    fallback = {name: items[:cap] for name, (items, cap) in pools.items()}

    needs_selection = {name: (items, cap) for name, (items, cap) in pools.items() if len(items) > cap}
    if not topic or not needs_selection:
        return fallback

    sections = []
    for name, (items, cap) in needs_selection.items():
        listing = "\n".join(f"  {i}. {item}" for i, item in enumerate(items, 1))
        sections.append(f"{name} (pick up to {cap}):\n{listing}")

    prompt = f"""
A marketing post is being written about this topic: "{topic}"

For each pool below, select the item NUMBERS most relevant to the topic — the
strongest, most specific supporting evidence for a post on this exact topic.

{chr(10).join(sections)}

Return ONLY a JSON object mapping each pool name to an array of item numbers
(integers), most relevant first, no explanation:
{{"pool_name": [3, 1], ...}}
"""

    result = llm.complete_json(prompt, model=llm.MODEL_LIGHT, max_tokens=1000, retries=1)
    if not isinstance(result, dict):
        return fallback

    selected = dict(fallback)
    for name, (items, cap) in needs_selection.items():
        numbers = result.get(name)
        if not isinstance(numbers, list):
            continue
        picked = []
        for n in numbers:
            try:
                idx = int(n)
            except (TypeError, ValueError):
                continue
            if 1 <= idx <= len(items):
                picked.append(items[idx - 1])
        if picked:
            selected[name] = picked[:cap]
    return selected


def brain_to_context(brain: dict, product_name: str = None, topic: str = None) -> str:
    """Convert brain JSON into the context string for the strategy agent.
    When topic is given, quotes/metrics/case studies/offers are selected for
    relevance to that specific post rather than always the same first few."""

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

    pools = {name: (brain.get(name) or [], cap) for name, cap in _CONTEXT_POOLS}
    pools["key_metrics"] = (metrics, 10)  # product focus may have swapped the pool
    sel = _select_relevant(pools, topic)

    consumer_sections = ""
    if sel["offers_pricing"]:
        consumer_sections += f"""
OFFERS & PRICING:
{nl.join([f"  - {o}" for o in sel["offers_pricing"]])}
"""
    if sel["customer_pain_points"]:
        consumer_sections += f"""
CUSTOMER PAIN POINTS (what the brand solves for people):
{nl.join([f"  - {p}" for p in sel["customer_pain_points"]])}
"""
    if sel["brand_promises"]:
        consumer_sections += f"""
BRAND PROMISES (outcomes stated to the customer):
{nl.join([f"  - {b}" for b in sel["brand_promises"]])}
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
{nl.join([f"  - {m}" for m in sel["key_metrics"]]) or "  - None"}

VALUE PROPOSITIONS:
{nl.join([f"  - {v}" for v in brain.get("value_propositions", [])]) or "  - None"}
{consumer_sections}
CUSTOMER QUOTES (use verbatim):
{nl.join([f"  - {q}" for q in sel["customer_quotes"]]) or "  - None"}

CASE STUDY RESULTS:
{nl.join([f"  - {c}" for c in sel["case_study_results"]]) or "  - None"}

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
    url = sys.argv[1] if len(sys.argv) > 1 else input("Enter website URL: ").strip()

    brain = build_brain(url)

    if brain and brain.get("products"):
        first = brain["products"][0]["name"]
        print(f"\n--- Brain context preview ({first}) ---")
        print(brain_to_context(brain, product_name=first))
