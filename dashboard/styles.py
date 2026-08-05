from __future__ import annotations

import streamlit as st


def apply_dashboard_styles(is_dark: bool = True) -> None:
    if is_dark:
        tokens = {
            "bg": "#070A0F",
            "surface": "rgba(255,255,255,0.06)",
            "surface_2": "rgba(255,255,255,0.09)",
            "surface_strong": "rgba(255,255,255,0.10)",
            "border": "rgba(255,255,255,0.12)",
            "text": "#F4F7FA",
            "muted": "#A7B0BC",
            "shadow": "rgba(0,0,0,0.30)",
            "app_bg": "linear-gradient(180deg, #070A0F, #05070B)",
            "header_bg": "rgba(7,10,15,0.96)",
            "chart_grid": "rgba(167,176,188,0.18)",
        }
    else:
        tokens = {
            "bg": "#F7FAFC",
            "surface": "#FFFFFF",
            "surface_2": "#F1F5F9",
            "surface_strong": "#E8EEF5",
            "border": "#D8E1EA",
            "text": "#0F172A",
            "muted": "#526173",
            "shadow": "rgba(15,23,42,0.09)",
            "app_bg": "linear-gradient(180deg, #F7FAFC, #EDF3F9)",
            "header_bg": "rgba(247,250,252,0.96)",
            "chart_grid": "rgba(82,97,115,0.18)",
        }

    st.markdown(
        f"""
<style>
    :root {{
        --dash-bg: {tokens["bg"]};
        --dash-surface: {tokens["surface"]};
        --dash-surface-2: {tokens["surface_2"]};
        --dash-surface-strong: {tokens["surface_strong"]};
        --dash-border: {tokens["border"]};
        --dash-text: {tokens["text"]};
        --dash-muted: {tokens["muted"]};
        --dash-accent: #00A7C8;
        --dash-red: #E82127;
        --dash-cyan: #00D1FF;
        --dash-success: #31D0AA;
        --dash-warning: #FFB020;
        --dash-danger: #FF4D4F;
        --dash-chart-grid: {tokens["chart_grid"]};
    }}

    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {{
        background: {tokens["app_bg"]} !important;
    }}

    .dashboard-shell {{
        color: var(--dash-text);
    }}

    [data-testid="stAppViewContainer"] .block-container,
    [data-testid="stAppViewContainer"] .stMarkdown,
    [data-testid="stAppViewContainer"] label,
    [data-testid="stAppViewContainer"] p {{
        color: var(--dash-text);
    }}

    [data-testid="stSidebar"] {{
        background: var(--dash-bg) !important;
        border-right: 1px solid var(--dash-border);
    }}

    [data-testid="stSidebar"] * {{
        color: var(--dash-text) !important;
    }}

    [data-testid="stSidebar"] button {{
        background: var(--dash-surface) !important;
        border: 1px solid var(--dash-border) !important;
        color: var(--dash-text) !important;
        border-radius: 8px !important;
        font-weight: 550 !important;
    }}

    [data-testid="stSidebar"] button:hover {{
        background: var(--dash-surface-2) !important;
        border-color: rgba(0,167,200,0.45) !important;
    }}

    [data-testid="stSidebar"] button[kind="primary"] {{
        background: rgba(0,167,200,0.16) !important;
        border-color: rgba(0,167,200,0.70) !important;
        box-shadow: inset 3px 0 0 var(--dash-accent);
    }}

    [data-testid="stSidebar"] a {{
        border-radius: 8px;
    }}

    [data-testid="stSidebar"] a[href] {{
        display: block;
        padding: 0.48rem 0.7rem !important;
        margin: 0.1rem 0 0.25rem;
        background: var(--dash-surface) !important;
        border: 1px solid var(--dash-border) !important;
        text-decoration: none !important;
    }}

    [data-testid="stSidebar"] a[href]:hover {{
        background: var(--dash-surface-2) !important;
        border-color: rgba(0,167,200,0.45) !important;
    }}

    [data-testid="stHeader"] {{
        background: {tokens["header_bg"]} !important;
        border-bottom: 1px solid var(--dash-border);
    }}

    .dash-hero {{
        padding: 1.4rem 1.5rem;
        border: 1px solid var(--dash-border);
        border-radius: 10px;
        background: var(--dash-surface);
        box-shadow: 0 18px 45px {tokens["shadow"]};
        margin-bottom: 1rem;
    }}

    .dash-hero h1 {{
        margin: 0;
        font-size: clamp(1.55rem, 2vw, 2.25rem);
        letter-spacing: 0;
        color: var(--dash-text);
    }}

    .dash-hero p {{
        margin: 0.35rem 0 0;
        color: var(--dash-muted);
        font-size: 0.98rem;
    }}

    .dash-sync {{
        margin-top: 0.9rem;
        color: var(--dash-accent);
        font-size: 0.85rem;
    }}

    .dash-card {{
        border: 1px solid var(--dash-border);
        border-radius: 8px;
        background: var(--dash-surface);
        padding: 1rem;
        min-height: 7rem;
        transition: transform 120ms ease, border-color 120ms ease;
    }}

    .dash-kpi-grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: clamp(4px, 1.5vw, 10px);
        width: 100%;
        max-width: 100%;
        box-sizing: border-box;
    }}

    .dash-kpi-card {{
        min-width: 0;
        width: 100%;
        min-height: clamp(82px, 24vw, 112px);
        box-sizing: border-box;
        border-radius: clamp(8px, 2vw, 14px);
        border: 1px solid var(--dash-border);
        background: var(--dash-surface);
        box-shadow: 0 6px 18px {tokens["shadow"]};
        padding: clamp(8px, 2.2vw, 18px);
        overflow: hidden;
    }}

    .dash-kpi-card:hover {{
        border-color: rgba(0,167,200,0.45);
    }}

    .dash-kpi-top {{
        display: flex;
        align-items: center;
        gap: clamp(3px, 1vw, 7px);
        min-width: 0;
    }}

    .dash-kpi-icon {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: clamp(18px, 5vw, 28px);
        height: clamp(18px, 5vw, 28px);
        border-radius: 6px;
        color: var(--dash-accent);
        background: rgba(0,167,200,0.12);
        font-size: clamp(11px, 3vw, 16px);
        flex: 0 0 auto;
    }}

    .dash-kpi-title {{
        color: var(--dash-muted);
        font-size: clamp(10px, 2.6vw, 14px);
        line-height: 1.25;
        font-weight: 550;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
    }}

    .dash-kpi-big {{
        color: var(--dash-text);
        font-size: clamp(20px, 6vw, 34px);
        line-height: 1.05;
        font-weight: 800;
        margin-top: clamp(6px, 1.4vw, 10px);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}

    .dash-kpi-caption {{
        color: var(--dash-muted);
        font-size: clamp(9px, 2.4vw, 13px);
        line-height: 1.2;
        margin-top: clamp(2px, 0.7vw, 4px);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}

    .dash-card:hover {{
        transform: translateY(-2px);
        border-color: rgba(0,209,255,0.35);
    }}

    .dash-kpi-label {{
        color: var(--dash-muted);
        font-size: 0.82rem;
        margin-bottom: 0.4rem;
    }}

    .dash-kpi-value {{
        color: var(--dash-text);
        font-size: 1.65rem;
        font-weight: 700;
        line-height: 1.15;
    }}

    .dash-kpi-note {{
        color: var(--dash-muted);
        font-size: 0.78rem;
        margin-top: 0.45rem;
    }}

    .dash-section-title {{
        margin: 1.4rem 0 0.7rem;
        color: var(--dash-text);
        font-size: 1.05rem;
        font-weight: 650;
        border-left: 3px solid var(--dash-red);
        padding-left: 0.7rem;
    }}

    .dash-panel {{
        border: 1px solid var(--dash-border);
        border-radius: 8px;
        background: var(--dash-surface);
        padding: 1rem;
        margin-bottom: 1rem;
    }}

    .dash-filter-title {{
        color: var(--dash-text);
        font-size: 0.95rem;
        font-weight: 650;
        margin-bottom: 0.7rem;
    }}

    .dash-empty, .dash-error {{
        border: 1px solid var(--dash-border);
        border-radius: 8px;
        background: var(--dash-surface);
        padding: 1rem;
        color: var(--dash-muted);
    }}

    .dash-error {{
        border-color: rgba(255,77,79,0.45);
        color: var(--dash-danger);
    }}

    .dash-timeline-item {{
        border-left: 2px solid var(--dash-cyan);
        padding: 0 0 0.9rem 0.9rem;
        margin-left: 0.35rem;
        color: var(--dash-text);
    }}

    .dash-timeline-meta {{
        color: var(--dash-muted);
        font-size: 0.86rem;
    }}

    div[data-testid="stMetric"] {{
        border: 1px solid var(--dash-border);
        border-radius: 8px;
        background: var(--dash-surface);
        padding: 0.75rem;
    }}

    div[data-testid="stDataFrame"] {{
        border: 1px solid var(--dash-border);
        border-radius: 8px;
        overflow: hidden;
    }}

    @media (max-width: 900px) {{
        .dash-card {{
            min-height: 5.8rem;
        }}
        .dash-hero {{
            padding: 1.1rem;
        }}
    }}
</style>
""",
        unsafe_allow_html=True,
    )
