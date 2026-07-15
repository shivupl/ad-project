import streamlit as st

from layer2_generation.graphic_generator import run
from paths import DATA_DIR, ROOT

st.set_page_config(page_title="Generation", layout="wide")
st.title("Layer 2 — Generation")
st.caption("topic + brand/brain → strategy brief → caption + graphic")

data_files = sorted(DATA_DIR.glob("*.json"))
brand_files = [f for f in data_files if f.name.startswith("brand_")]
brain_files = [f for f in data_files if f.name.startswith("brain_")]

default_logo = ROOT / "logo.png"

with st.sidebar:
    st.header("Inputs")
    topic = st.text_input("Topic", placeholder="e.g. CreditX deployment speed")
    product_name = st.text_input("Product (optional)", placeholder="e.g. CreditX")
    brand_file = st.selectbox(
        "Brand JSON",
        brand_files,
        format_func=lambda p: p.name,
        index=0 if brand_files else None,
    )
    brain_file = st.selectbox(
        "Brain JSON",
        brain_files,
        format_func=lambda p: p.name,
        index=0 if brain_files else None,
    )
    logo_path = st.text_input("Logo path", value=str(default_logo))
    generate = st.button("Generate", type="primary")

if not brand_files or not brain_files:
    st.warning("Run **Extraction** first to create brand and brain JSON files in `data/`.")
    st.stop()

if generate:
    if not topic.strip():
        st.error("Enter a topic.")
        st.stop()

    with st.spinner("Generating brief and graphic..."):
        try:
            result = run(
                topic=topic.strip(),
                brand_path=str(brand_file),
                brain_path=str(brain_file),
                logo_path=logo_path,
                product_name=product_name.strip() or None,
            )
        except Exception as e:
            st.error(str(e))
            st.stop()

    st.success("Done!")

    if result.get("critique"):
        with st.expander("🎨 Senior designer review", expanded=False):
            st.markdown(result["critique"])

    if result.get("warnings"):
        with st.expander(f"⚠️ {len(result['warnings'])} validation warning(s)", expanded=True):
            for w in result["warnings"]:
                st.markdown(f"- {w}")

    tab_caption, tab_graphic, tab_brief = st.tabs(["Caption", "Graphic", "Brief"])

    with tab_caption:
        st.text_area("LinkedIn post text", result["caption"], height=300)
        st.caption(f"Saved to `{result['caption_path']}`")

    with tab_graphic:
        if result.get("png_path"):
            st.image(result["png_path"])
            with open(result["png_path"], "rb") as f:
                st.download_button("Download PNG (ready to post)", f, file_name="graphic.png", mime="image/png")
            st.caption(f"PNG: `{result['png_path']}` · HTML: `{result['html_path']}`")
            with st.expander("HTML preview"):
                st.components.v1.html(result["html"], height=660, scrolling=True)
        else:
            st.components.v1.html(result["html"], height=680, scrolling=True)
            st.caption(f"Saved to `{result['html_path']}` (PNG render unavailable)")

    with tab_brief:
        st.json(result["brief"])
        st.caption(f"Saved to `{result['brief_path']}`")

else:
    st.info("Set a topic and click **Generate** in the sidebar.")
