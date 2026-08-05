from __future__ import annotations

import streamlit as st

THEME_PRESETS: dict[str, dict[str, str]] = {
    "dark": {
        "app_bg": "#0b0f16",
        "sidebar_bg": "#252631",
        "card_bg": "#171b22",
        "card_bg_alt": "#0b2530",
        "text": "#ffffff",
        "text_muted": "#b8c7d9",
        "border": "#303846",
        "primary": "#00a7c8",
        "input_bg": "#282933",
        "button_text": "#ffffff",
        "card_shadow": "none",
        "total_border": "rgba(0,167,200,0.5)",
    },
    "light": {
        "app_bg": "#f6f8fb",
        "sidebar_bg": "#f0f2f6",
        "card_bg": "#ffffff",
        "card_bg_alt": "#eaf7fb",
        "text": "#0f172a",
        "text_muted": "#475569",
        "border": "#d7dee8",
        "primary": "#007c99",
        "input_bg": "#ffffff",
        "button_text": "#ffffff",
        "card_shadow": "0 6px 18px rgba(15,23,42,0.06)",
        "total_border": "rgba(44,83,100,0.36)",
    },
}


def init_theme_state() -> None:
    if "ui_theme" not in st.session_state:
        st.session_state.ui_theme = "dark"


def set_theme_from_toggle() -> None:
    st.session_state.ui_theme = "dark" if st.session_state.dark_mode_toggle else "light"


def get_theme() -> dict[str, str]:
    return THEME_PRESETS.get(
        st.session_state.get("ui_theme", "dark"),
        THEME_PRESETS["dark"],
    )


def is_dark_theme() -> bool:
    return st.session_state.get("ui_theme", "dark") == "dark"


def apply_theme_css() -> None:
    t = get_theme()
    st.markdown(
        f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Kanit', sans-serif !important;
    }}

    :root {{
        --app-bg: {t["app_bg"]};
        --sidebar-bg: {t["sidebar_bg"]};
        --card-bg: {t["card_bg"]};
        --card-bg-alt: {t["card_bg_alt"]};
        --text-main: {t["text"]};
        --text-muted: {t["text_muted"]};
        --border-color: {t["border"]};
        --primary-color: {t["primary"]};
        --input-bg: {t["input_bg"]};
        --button-text: {t["button_text"]};
        --card-shadow: {t["card_shadow"]};
        --total-border: {t["total_border"]};
    }}

    /* ── App background ── */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {{
        background: var(--app-bg) !important;
    }}

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {{
        background: var(--sidebar-bg) !important;
    }}

    [data-testid="stSidebar"] * {{
        color: var(--text-main);
    }}

    section[data-testid="stSidebar"] div[data-testid="stExpander"] {{
        background: var(--sidebar-bg) !important;
        border: 1px solid var(--border-color) !important;
    }}

    section[data-testid="stSidebar"] a[href*="dashboard"] {{
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 0.45rem 0.65rem;
        background: rgba(44,83,100,0.08);
        text-decoration: none;
        font-weight: 500;
        transition: all 0.2s ease;
    }}

    section[data-testid="stSidebar"] a[href*="dashboard"]:hover {{
        background: rgba(44,83,100,0.16);
        border-color: rgba(44,83,100,0.55);
    }}

    /* ── Header banner — fixed dark gradient (branding) ── */
    .header-container {{
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        padding: 2.5rem 2rem;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.35);
        margin-bottom: 2rem;
        margin-top: 0.5rem;
    }}

    .header-title {{
        font-size: 2.2rem;
        font-weight: 600;
        margin: 0;
        letter-spacing: 0.5px;
        color: #ffffff !important;
    }}

    .header-subtitle {{
        font-size: 1.1rem;
        font-weight: 300;
        color: #e0e0e0 !important;
        margin-top: 0.5rem;
    }}

    /* ── Section titles ── */
    .section-title {{
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        color: var(--text-main) !important;
        border-bottom: 2px solid var(--border-color);
    }}

    /* ── Buttons ── */
    div.stButton > button:first-child {{
        font-family: 'Kanit', sans-serif;
        font-size: 1.1rem;
        font-weight: 500;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
    }}

    /* ── Inputs / selects ── */
    input, textarea, select {{
        background-color: var(--input-bg) !important;
        color: var(--text-main) !important;
        border-color: var(--border-color) !important;
    }}

    div[data-baseweb="select"] > div {{
        background-color: var(--input-bg) !important;
        color: var(--text-main) !important;
        border-color: var(--border-color) !important;
    }}

    /* ── Typography ── */
    h1, h2, h3, h4, h5, h6 {{
        color: var(--text-main) !important;
    }}

    hr {{
        border-color: var(--border-color) !important;
    }}

    /* ── Mini summary dashboard ── */
    .mini-dashboard-shell {{
        margin: -0.35rem 0 1.55rem;
    }}

    .mini-dashboard-title {{
        color: var(--text-main);
        font-size: 0.98rem;
        font-weight: 600;
        margin: 0 0 0.55rem;
    }}

    .mini-dashboard-wrap {{
        width: 100%;
        max-width: 100%;
        overflow-x: hidden;
        box-sizing: border-box;
    }}

    .mini-dashboard-grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: clamp(4px, 1.5vw, 10px);
        width: 100%;
        max-width: 100%;
        box-sizing: border-box;
    }}

    .mini-stat-card {{
        min-width: 0;
        width: 100%;
        min-height: clamp(82px, 24vw, 112px);
        box-sizing: border-box;
        border-radius: clamp(8px, 2vw, 14px);
        border: 1px solid var(--border-color);
        background: var(--card-bg);
        box-shadow: var(--card-shadow);
        padding: clamp(8px, 2.2vw, 18px);
        overflow: hidden;
    }}

    .mini-stat-card--total {{
        border-color: var(--total-border);
        background: var(--card-bg-alt);
    }}

    .mini-stat-top {{
        display: flex;
        align-items: center;
        gap: clamp(3px, 1vw, 7px);
        min-width: 0;
    }}

    .mini-stat-icon {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: clamp(18px, 5vw, 28px);
        height: clamp(18px, 5vw, 28px);
        border-radius: 6px;
        color: var(--primary-color);
        background: rgba(44,83,100,0.12);
        font-size: clamp(11px, 3vw, 16px);
        flex: 0 0 auto;
    }}

    .mini-stat-title {{
        color: var(--text-muted);
        font-size: clamp(10px, 2.6vw, 14px);
        line-height: 1.25;
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
    }}

    .mini-stat-value {{
        color: var(--text-main);
        font-size: clamp(20px, 6vw, 34px);
        line-height: 1.05;
        font-weight: 800;
        margin-top: clamp(6px, 1.4vw, 10px);
    }}

    .mini-stat-subtitle {{
        color: var(--text-muted);
        font-size: clamp(9px, 2.4vw, 13px);
        line-height: 1.2;
        margin-top: clamp(2px, 0.7vw, 4px);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}

    .mini-dashboard-error {{
        border: 1px solid rgba(239,68,68,0.35);
        border-radius: 10px;
        padding: 0.85rem 1rem;
        color: #dc2626;
        background: rgba(239,68,68,0.08);
    }}
</style>
""",
        unsafe_allow_html=True,
    )
