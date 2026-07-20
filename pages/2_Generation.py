import json
from pathlib import Path

import streamlit as st

from layer2_generation.graphic_generator import render_from_brief
from layer2_generation.strategy_agent import generate_brief, fit_brief_copy, brief_to_summary
from paths import DATA_DIR, ROOT

st.set_page_config(page_title="Generation", layout="wide")
st.title("Layer 2 — Generation")
st.caption("topic + brand/brain → propose idea → review / tweak → generate graphic")

data_files = sorted(DATA_DIR.glob("*.json"))
brand_files = [f for f in data_files if f.name.startswith("brand_")]
brain_files = [f for f in data_files if f.name.startswith("brain_")]
default_logo = ROOT / "logo.png"

with st.sidebar:
    st.header("Inputs")
    topic = st.text_input("Topic", placeholder="e.g. CreditX deployment speed")
    product_name = st.text_input("Product (optional)", placeholder="e.g. CreditX")
    brand_file = st.selectbox("Brand JSON", brand_files, format_func=lambda p: p.name,
                              index=0 if brand_files else None)
    brain_file = st.selectbox("Brain JSON", brain_files, format_func=lambda p: p.name,
                              index=0 if brain_files else None)
    brand_logo = None
    if brand_file:
        try:
            brand_logo = (json.load(open(brand_file)).get("visual_identity") or {}).get("logo_path")
        except Exception:
            pass
    logo_default = brand_logo if brand_logo and Path(brand_logo).exists() else str(default_logo)
    logo_path = st.text_input("Logo path", value=logo_default)
    propose = st.button("① Propose idea", type="primary")

if not brand_files or not brain_files:
    st.warning("Run **Extraction** first to create brand and brain JSON files in `data/`.")
    st.stop()

def _sig():
    return (str(brand_file), str(brain_file), topic.strip(), product_name.strip())

# ── Step 1: propose ──
if propose:
    if not topic.strip():
        st.error("Enter a topic."); st.stop()
    with st.spinner("Drafting a proposed idea..."):
        try:
            brain = json.load(open(brain_file)); brand = json.load(open(brand_file))
            brief = generate_brief(topic.strip(), brain, brand=brand,
                                   product_name=product_name.strip() or None)
        except Exception as e:
            st.error(str(e)); st.stop()
    if not brief:
        st.error("Couldn't draft an idea — try again."); st.stop()
    st.session_state.proposal = brief
    st.session_state.proposal_sig = _sig()
    st.session_state.pop("result", None)

proposal = st.session_state.get("proposal")

# ── Step 2: review / tweak / regenerate / generate ──
if proposal:
    if st.session_state.get("proposal_sig") != _sig():
        st.warning("Inputs changed since this idea was proposed — click **① Propose idea** to refresh.")

    st.subheader("Proposed idea")
    st.markdown(brief_to_summary(proposal))

    steer = st.text_input("Steer a different idea (optional)",
                          placeholder="e.g. lean more on cost savings")
    if st.button("🔄 Try a different idea"):
        with st.spinner("Drafting a different idea..."):
            new = None
            try:
                brain = json.load(open(brain_file)); brand = json.load(open(brand_file))
                new = generate_brief(topic.strip(), brain, brand=brand,
                                     product_name=product_name.strip() or None,
                                     steer=steer.strip() or None)
            except Exception as e:
                st.warning(f"Regenerate failed, keeping current idea: {e}")
        if new:
            st.session_state.proposal = new
            st.session_state.proposal_sig = _sig()
            st.session_state.pop("result", None)
            st.rerun()

    with st.expander("✏️ Tweak the idea"):
        g = proposal.get("graphic") or {}
        c = proposal.get("caption") or {}
        with st.form("tweak_form"):
            st.markdown("**Graphic copy**")
            headline = st.text_input("Headline", g.get("headline", ""))
            stat_hero = st.text_input("Hero stat", g.get("stat_hero", ""))
            contrast_line = st.text_input("Contrast line", g.get("contrast_line", ""))
            subtext = st.text_input("Subtext", g.get("subtext", ""))
            metrics_text = st.text_area("Metrics (one per line)",
                                        "\n".join(str(m) for m in (g.get("metrics") or [])))
            cta = st.text_input("CTA", g.get("cta", ""))
            design_notes = st.text_area("Layout note (optional)", g.get("design_notes", ""))
            st.markdown("**Caption**")
            hook = st.text_input("Hook", c.get("hook", ""))
            body = st.text_area("Body", c.get("body", ""))
            cap_cta = st.text_input("Caption CTA", c.get("cta", ""))
            applied = st.form_submit_button("Apply tweaks")
        if applied:
            if not (headline.strip() and cta.strip()):
                st.error("Headline and CTA can't be empty.")
            else:
                edited = dict(proposal)
                edited["graphic"] = {**g, "headline": headline, "stat_hero": stat_hero,
                                     "contrast_line": contrast_line, "subtext": subtext,
                                     "metrics": [m.strip() for m in metrics_text.splitlines() if m.strip()],
                                     "cta": cta, "design_notes": design_notes}
                edited["caption"] = {**c, "hook": hook, "body": body, "cta": cap_cta}
                fitted, changes = fit_brief_copy(edited)
                st.session_state.proposal = fitted
                st.session_state.proposal_sig = _sig()
                st.session_state.pop("result", None)
                if changes:
                    st.info("Adjusted to fit:\n" + "\n".join(f"- {ch}" for ch in changes))
                st.rerun()

    st.divider()
    if st.button("② Generate graphic", type="primary"):
        with st.spinner("Generating graphic..."):
            try:
                brand = json.load(open(brand_file))
                st.session_state.result = render_from_brief(
                    st.session_state.proposal, brand, logo_path,
                    product_name=product_name.strip() or None)
            except Exception as e:
                st.error(str(e)); st.stop()

# ── result display ──
result = st.session_state.get("result")
if result:
    st.success("Done!")
    if result.get("design_skill"):
        st.caption(f"Design skill: `{result['design_skill']}` (routed by marketing profile)")
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
            if result.get("draft_png_path"):
                with st.expander("Before / after defect repair"):
                    col_before, col_after = st.columns(2)
                    with col_before:
                        st.markdown("**Before** (initial draft)"); st.image(result["draft_png_path"])
                    with col_after:
                        st.markdown("**After** (shipped)"); st.image(result["png_path"])
            with st.expander("HTML preview"):
                st.components.v1.html(result["html"], height=660, scrolling=True)
        else:
            st.components.v1.html(result["html"], height=680, scrolling=True)
            st.caption(f"Saved to `{result['html_path']}` (PNG render unavailable)")
    with tab_brief:
        st.json(result["brief"])
        st.caption(f"Saved to `{result['brief_path']}`")
elif not proposal:
    st.info("Set a topic and click **① Propose idea** in the sidebar.")
