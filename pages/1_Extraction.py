import streamlit as st

from layer1_extraction.extract_brain import brain_to_context, build_brain
from layer1_extraction.extract_brand import brand_to_prompt, build_brand
from paths import DATA_DIR, ROOT

st.set_page_config(page_title="Extraction", layout="wide")
st.title("Layer 1 — Extraction")
st.caption("URL → brand JSON (visual identity) + brain JSON (company knowledge)")

url = st.text_input("Website URL", placeholder="https://www.finbots.ai/")
max_pages = st.slider("Max pages to crawl (brain only)", min_value=5, max_value=50, value=20, step=5)

logo_file = st.file_uploader("Logo (optional — used for brand JSON)", type=["png", "jpg", "jpeg", "webp"])

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
            logo_path = str(ROOT / "logo.png")
            with open(logo_path, "wb") as f:
                f.write(logo_file.getbuffer())
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

            c1, c2, c3 = st.columns(3)
            color_fields = [("Primary", "primary_color"), ("Secondary", "secondary_color"), ("Accent", "accent_color")]
            for col, (label, key) in zip([c1, c2, c3], color_fields):
                color = vi.get(key) or "#cccccc"
                with col:
                    st.color_picker(label, value=color, disabled=True)

            tab_json, tab_prompt = st.tabs(["Brand JSON", "Brand prompt preview"])
            with tab_json:
                st.json(brand)
            with tab_prompt:
                st.code(brand_to_prompt(brand), language=None)

if extract_brain:
    if not url.strip():
        st.error("Enter a website URL.")
    else:
        with st.spinner(f"Crawling site (up to {max_pages} pages) and extracting knowledge... This may take a few minutes."):
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
