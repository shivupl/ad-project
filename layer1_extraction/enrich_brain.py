import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anthropic
import base64
import json
import os
import re
from datetime import date
from dotenv import load_dotenv

from layer1_extraction.extract_brain import BRAIN_SCHEMA_PROMPT, run_brain_extraction
from paths import DATA_DIR

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}
MAX_PDF_BYTES = 30 * 1024 * 1024  # stay under the API's 32 MB request cap


# ─────────────────────────────────────────────
# STEP 1: Load documents as Claude content blocks
# ─────────────────────────────────────────────

def load_document_block(path: str) -> dict:
    """PDF → native base64 document block (Claude reads it directly, including
    slide layouts). .txt/.md → plain text block with a filename header.
    Raises ValueError on unsupported extension or oversized PDF."""
    p = Path(path)
    ext = p.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}' for {p.name} — supported: {sorted(SUPPORTED_EXTENSIONS)} (export decks/docs to PDF)")

    if ext == ".pdf":
        data = p.read_bytes()
        if len(data) > MAX_PDF_BYTES:
            raise ValueError(f"{p.name} is {len(data) / 1024 / 1024:.0f} MB — PDFs must be under 30 MB")
        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.standard_b64encode(data).decode(),
            },
        }

    text = p.read_text(errors="replace")
    return {"type": "text", "text": f"--- DOCUMENT: {p.name} ---\n{text}"}


# ─────────────────────────────────────────────
# STEP 2: Extract knowledge from documents
# ─────────────────────────────────────────────

def extract_from_documents(doc_paths: list, company_name: str) -> dict:
    """Extract structured company knowledge from the given documents using the
    same schema as website extraction. Returns {} on failure."""
    print(f"Extracting knowledge from {len(doc_paths)} document(s)...")

    content = [load_document_block(p) for p in doc_paths]
    content.append({
        "type": "text",
        "text": f"""
You are a marketing knowledge analyst. Extract structured company knowledge about
{company_name} from the attached documents (pitch decks, PDFs, internal notes),
for use by a marketing AI agent.
{BRAIN_SCHEMA_PROMPT}""",
    })

    return run_brain_extraction(content)


# ─────────────────────────────────────────────
# STEP 3: Merge document knowledge into the existing brain
# ─────────────────────────────────────────────

def merge_brains(base: dict, incoming: dict) -> dict:
    """LLM-assisted merge of two brain JSONs about the same company: union with
    semantic dedupe, preferring the more specific variant on conflicts.
    On any failure returns base unchanged — a merge hiccup must never destroy
    the existing brain."""
    print("Merging document knowledge into existing brain...")

    sources = base.get("sources")  # provenance is code-managed, never the model's job
    base_for_merge = {k: v for k, v in base.items() if k != "sources"}

    prompt = f"""
You are merging two knowledge bases about the same company into one. BASE was
extracted from the company's website; INCOMING was extracted from internal
documents (decks, PDFs, notes).

BASE:
{json.dumps(base_for_merge, indent=2)}

INCOMING:
{json.dumps(incoming, indent=2)}

Merge rules:
- Union all list fields. Deduplicate semantic near-duplicates — if the same fact
  appears in both with different wording, keep it ONCE. When duplicate facts
  conflict on specifics (e.g. different numbers for the same claim), keep the
  more specific / more quantified variant — internal documents are usually more
  precise than website copy.
- Merge products BY NAME: if both sources describe the same product, union its
  key_features, use_cases, and metrics (deduplicated). Products that appear in
  only one source are kept whole. Never create duplicate product entries for
  the same product under slightly different names.
- customer_quotes stay verbatim from both sources — never paraphrase, never
  merge two different quotes into one.
- Scalar fields (company_name, tagline, industry, industry_slug, target_audience,
  icp, tone): keep BASE's value unless INCOMING's is clearly more specific.
- The output must use the exact same JSON structure as BASE.

Return ONLY the merged JSON object, no explanation, no markdown, no backticks.
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=8000,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}],
        )

        if response.stop_reason == "max_tokens":
            print("Warning: merge response hit max_tokens — keeping existing brain unchanged")
            return base

        raw = response.content[0].text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'^```\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        merged = json.loads(raw)
        if not isinstance(merged, dict) or not merged.get("company_name"):
            print("Merge produced invalid output — keeping existing brain unchanged")
            return base

        if sources:
            merged["sources"] = sources
        return merged

    except Exception as e:
        print(f"Merge failed, keeping existing brain unchanged: {e}")
        return base


# ─────────────────────────────────────────────
# STEP 4: Full enrichment pipeline
# ─────────────────────────────────────────────

def enrich_brain(brain_path: str, doc_paths: list) -> dict:
    """Pipeline: load brain → extract from documents → merge → save back in place.
    Returns the (possibly enriched) brain."""
    with open(brain_path) as f:
        base = json.load(f)

    incoming = extract_from_documents(doc_paths, base.get("company_name", "the company"))
    if not incoming:
        print("Document extraction failed — brain left unchanged")
        return base

    merged = merge_brains(base, incoming)

    if merged is not base:
        merged.setdefault("sources", [])
        for p in doc_paths:
            merged["sources"].append({
                "type": "document",
                "ref": Path(p).name,
                "added": date.today().isoformat(),
            })

        with open(brain_path, "w") as f:
            json.dump(merged, f, indent=2)
        print(f"\nEnriched brain saved → {brain_path}")

    return merged


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python layer1_extraction/enrich_brain.py <brain_json_path> <doc1> [doc2 ...]")
        sys.exit(1)

    brain_path = sys.argv[1]
    doc_paths = sys.argv[2:]

    brain = enrich_brain(brain_path, doc_paths)
    print(json.dumps(brain, indent=2))
