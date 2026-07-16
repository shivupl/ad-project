import json

import streamlit as st

from layer1_extraction.enrich_brain import enrich_brain
from layer1_extraction.extract_brain import brain_to_context, build_brain
from layer1_extraction.extract_brand import brand_to_prompt, build_brand
from paths import DATA_DIR, ROOT

st.set_page_config(page_title="Extraction", layout="wide")
st.title("Layer 1 — Extraction")
st.caption("URL → brand JSON (visual identity) + brain JSON (company knowledge)")

url = st.text_input("Website URL", placeholder="https://www.finbots.ai/")
max_pages = st.slider("Pages to analyze (most relevant, not a raw crawl limit)", min_value=5, max_value=30, value=12, step=1)

logo_file = st.file_uploader(
    "Logo (optional — auto-fetched from the site; upload only to override)",
    type=["png", "jpg", "jpeg", "webp"],
)

col_brand, col_brain = st.columns(2)

with col_brand:
    extract_brand = st.button("Extract Brand", type="primary", use_container_width=True)

with col_brain:
    extract_brain = st.button("Extract Brain", type="primary", use_container_width=True)

st.divider()

if extract_brand:
    if not url.strip():
        st.error("Enter a website URL.")
    else:
        logo_path = None
        if logo_file:
            # Normalize whatever was uploaded to a real PNG — the pipeline
            # hardcodes image/png, so mislabeled JPEG bytes would break it.
            import io
            from PIL import Image
            logo_path = str(ROOT / "logo.png")
            Image.open(io.BytesIO(logo_file.getbuffer())).save(logo_path, format="PNG")
            st.caption(f"Logo saved → `{logo_path}`")

        with st.spinner("Scraping homepage and extracting brand identity..."):
            try:
                brand = build_brand(url.strip(), logo_path=logo_path)
            except Exception as e:
                st.error(str(e))
                st.stop()

        if not brand:
            st.error("Brand extraction failed.")
        else:
            slug = brand.get("company_name", "company").lower().replace(" ", "_").replace(".", "").replace("/", "")
            output_path = DATA_DIR / f"brand_{slug}.json"
            st.success(f"Brand saved → `{output_path}`")

            vi = brand.get("visual_identity", {})
            bp = brand.get("brand_personality", {})

            if vi.get("logo_path"):
                lc1, lc2 = st.columns([1, 5])
                lc1.image(vi["logo_path"], width=100)
                lc2.caption(f"Logo: `{vi['logo_path']}`")
            else:
                st.warning("No logo found on the site — upload one above and re-extract, or set a logo path on the Generation page.")

            c1, c2, c3 = st.columns(3)
            color_fields = [("Primary", "primary_color"), ("Secondary", "secondary_color"), ("Accent", "accent_color")]
            for col, (label, key) in zip([c1, c2, c3], color_fields):
                color = vi.get(key) or "#cccccc"
                with col:
                    st.color_picker(label, value=color, disabled=True)

            mp = brand.get("marketing_profile") or {}
            if mp:
                st.subheader("Marketing profile")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Business model", mp.get("business_model") or "—")
                m2.metric("Persuasion", mp.get("persuasion_mode") or "—")
                m3.metric("Density", mp.get("content_density") or "—")
                m4.metric("CTA style", mp.get("cta_style") or "—")
                if mp.get("reasoning"):
                    st.caption(f"Why: {mp['reasoning']}")

            tab_json, tab_prompt = st.tabs(["Brand JSON", "Brand prompt preview"])
            with tab_json:
                st.json(brand)
            with tab_prompt:
                st.code(brand_to_prompt(brand), language=None)

if extract_brain:
    if not url.strip():
        st.error("Enter a website URL.")
    else:
        with st.spinner(f"Discovering and ranking pages, then extracting knowledge from the top {max_pages}... This may take a few minutes."):
            try:
                brain = build_brain(url.strip(), max_pages=max_pages)
            except Exception as e:
                st.error(str(e))
                st.stop()

        if not brain:
            st.error("Brain extraction failed.")
        else:
            slug = brain.get("company_name", "company").lower().replace(" ", "_").replace(".", "").replace("/", "")
            output_path = DATA_DIR / f"brain_{slug}.json"
            st.success(f"Brain saved → `{output_path}`")

            products = brain.get("products", [])
            if products:
                st.subheader("Products")
                for p in products:
                    with st.expander(p.get("name", "Product"), expanded=len(products) == 1):
                        st.write(p.get("description", ""))
                        if p.get("metrics"):
                            st.markdown("**Metrics**")
                            for m in p["metrics"]:
                                st.markdown(f"- {m}")

            tab_json, tab_context = st.tabs(["Brain JSON", "Strategy context preview"])
            with tab_json:
                st.json(brain)
            with tab_context:
                product_name = products[0]["name"] if products else None
                st.code(brain_to_context(brain, product_name=product_name), language=None)

if not extract_brand and not extract_brain:
    st.info("Enter a URL, then run **Extract Brand** and/or **Extract Brain**.")

    existing = sorted(DATA_DIR.glob("*.json"))
    if existing:
        st.subheader("Existing data files")
        for f in existing:
            st.markdown(f"- `{f.name}`")

st.divider()
st.subheader("Enrich brain with documents")
st.caption("Pitch decks, PDFs, notes → extracted with the same schema, merged into an existing brain (deduplicated)")

brain_files = sorted(DATA_DIR.glob("brain_*.json"))

if not brain_files:
    st.info("Run **Extract Brain** first — enrichment needs an existing brain JSON to merge into.")
else:
    target_brain = st.selectbox("Brain to enrich", brain_files, format_func=lambda p: p.name)
    doc_files = st.file_uploader(
        "Documents (PDF, .txt, .md — export decks/docs to PDF)",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
    )
    enrich = st.button("Enrich Brain", type="primary")

    if enrich:
        if not doc_files:
            st.error("Upload at least one document.")
        else:
            uploads_dir = DATA_DIR / "uploads"
            uploads_dir.mkdir(exist_ok=True)

            doc_paths = []
            for f in doc_files:
                path = uploads_dir / f.name
                with open(path, "wb") as out:
                    out.write(f.getbuffer())
                doc_paths.append(str(path))

            before = json.load(open(target_brain))

            with st.spinner(f"Extracting from {len(doc_paths)} document(s) and merging into {target_brain.name}..."):
                try:
                    merged = enrich_brain(str(target_brain), doc_paths)
                except Exception as e:
                    st.error(str(e))
                    st.stop()

            if merged == before:
                st.warning("Enrichment made no changes (extraction or merge failed — brain left unchanged).")
            else:
                st.success(f"Enriched brain saved → `{target_brain}`")

                count_fields = [
                    "products", "key_metrics", "offers_pricing", "customer_pain_points",
                    "brand_promises", "customer_quotes", "notable_clients",
                    "case_study_results", "differentiators", "key_messages",
                ]
                rows = []
                for field in count_fields:
                    b = len(before.get(field) or [])
                    a = len(merged.get(field) or [])
                    rows.append({"field": field, "before": b, "after": a, "added": a - b})
                st.table(rows)

                with st.expander("Enriched brain JSON"):
                    st.json(merged)
