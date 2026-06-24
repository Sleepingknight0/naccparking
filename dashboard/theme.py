from __future__ import annotations

import streamlit as st


def init_theme_state() -> None:
    if "ui_theme" not in st.session_state:
        st.session_state.ui_theme = "dark"


def is_dark_theme() -> bool:
    return st.session_state.get("ui_theme", "dark") == "dark"
