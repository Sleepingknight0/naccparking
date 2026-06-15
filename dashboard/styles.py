from __future__ import annotations

import streamlit as st


def apply_dashboard_styles(is_dark: bool = True) -> None:
    if is_dark:
        tokens = {
            "bg": "#070A0F",
            "surface": "rgba(255,255,255,0.06)",
            "surface_strong": "rgba(255,255,255,0.10)",
            "border": "rgba(255,255,255,0.12)",
            "text": "#F4F7FA",
            "muted": "#A7B0BC",
            "shadow": "rgba(0,0,0,0.30)",
        }
    else:
        tokens = {
            "bg": "#0B1018",
            "surface": "rgba(255,255,255,0.075)",
            "surface_strong": "rgba(255,255,255,0.12)",
            "border": "rgba(255,255,255,0.14)",
            "text": "#F4F7FA",
            "muted": "#B5BFCC",
            "shadow": "rgba(0,0,0,0.24)",
        }

    st.markdown(
        f"""
<style>
    :root {{
        --dash-bg: {tokens["bg"]};
        --dash-surface: {tokens["surface"]};
        --dash-surface-strong: {tokens["surface_strong"]};
        --dash-border: {tokens["border"]};
        --dash-text: {tokens["text"]};
        --dash-muted: {tokens["muted"]};
        --dash-red: #E82127;
        --dash-cyan: #00D1FF;
        --dash-success: #31D0AA;
        --dash-warning: #FFB020;
        --dash-danger: #FF4D4F;
    }}

    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {{
        background: radial-gradient(circle at top right, rgba(0,209,255,0.14), transparent 30rem),
                    radial-gradient(circle at bottom left, rgba(232,33,39,0.08), transparent 28rem),
                    linear-gradient(180deg, var(--dash-bg), #05070B) !important;
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
        background: #0B1018 !important;
        border-right: 1px solid var(--dash-border);
    }}

    [data-testid="stSidebar"] * {{
        color: var(--dash-text) !important;
    }}

    [data-testid="stSidebar"] [aria-checked="true"],
    [data-testid="stSidebar"] a[aria-current="page"] {{
        background: rgba(0,209,255,0.12) !important;
        border-radius: 8px;
    }}

    [data-testid="stSidebar"] button {{
        background: rgba(44, 83, 100, 0.12) !important;
        border: 1px solid rgba(255,255,255,0.14) !important;
        color: var(--dash-text) !important;
        border-radius: 8px !important;
    }}

    [data-testid="stSidebar"] button:hover {{
        background: rgba(44, 83, 100, 0.22) !important;
        border-color: rgba(0,209,255,0.35) !important;
    }}

    [data-testid="stSidebar"] a {{
        border-radius: 8px;
    }}

    [data-testid="stSidebar"] a[href] {{
        display: block;
        padding: 0.48rem 0.7rem !important;
        margin: 0.1rem 0 0.25rem;
        background: rgba(44, 83, 100, 0.12) !important;
        border: 1px solid rgba(255,255,255,0.14) !important;
        text-decoration: none !important;
    }}

    [data-testid="stSidebar"] a[href]:hover {{
        background: rgba(44, 83, 100, 0.22) !important;
        border-color: rgba(0,209,255,0.35) !important;
    }}

    [data-testid="stHeader"] {{
        background: rgba(7,10,15,0.96) !important;
        border-bottom: 1px solid var(--dash-border);
    }}

    .dash-hero {{
        padding: 1.4rem 1.5rem;
        border: 1px solid var(--dash-border);
        border-radius: 10px;
        background: linear-gradient(135deg, rgba(255,255,255,0.09), rgba(255,255,255,0.025));
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
        color: var(--dash-cyan);
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
