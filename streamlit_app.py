import streamlit as st

extraction = st.Page("pages/1_Extraction.py", title="Extraction", icon="🔍", default=True)
generation = st.Page("pages/2_Generation.py", title="Generation", icon="🎨")

pg = st.navigation([extraction, generation])
pg.run()
