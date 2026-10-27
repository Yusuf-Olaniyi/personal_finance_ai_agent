from pathlib import Path

import streamlit as st

_CSS = Path(__file__).parent / "style.css"


def inject_css() -> None:
    st.markdown(f"<style>{_CSS.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)