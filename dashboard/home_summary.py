from __future__ import annotations

import html
from datetime import date, datetime

import pandas as pd
import streamlit as st


DATE_CANDIDATES = [
    "record_datetime",
    "date_key",
    "วันที่ตรวจพบ",
    "วันที่บันทึก",
    "วันที่พบ",
    "Timestamp",
    "Date",
    "created_at",
    "found_date",
]
BUILDING_CANDIDATES = ["อาคาร", "building", "สถานที่", "location", "building_name"]


def get_today_records(df: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=list(df.columns) if df is not None else [])

    today = today or datetime.now().date()
    date_col = _find_column(df, DATE_CANDIDATES)
    if date_col is None:
        return df.iloc[0:0].copy()

    parsed_dates = _parse_dates(df[date_col])
    return df[parsed_dates.dt.date == today].copy()


def get_today_building_counts(
    df: pd.DataFrame,
    buildings: list[str],
    today: date | None = None,
) -> list[dict[str, object]]:
    today_df = get_today_records(df, today=today)
    building_col = _find_column(today_df, BUILDING_CANDIDATES)
    if building_col is None:
        building_counts = pd.Series(dtype="int64")
    else:
        building_values = today_df[building_col].fillna("").astype(str).str.strip()
        building_counts = building_values.value_counts()

    cards = []
    for building in _first_five_buildings(buildings):
        if building:
            count = int(building_counts.get(str(building).strip(), 0))
            cards.append({"label": str(building).strip(), "count": count, "kind": "building"})
        else:
            cards.append({"label": "ยังไม่มีอาคาร", "count": 0, "kind": "empty"})

    cards.append({"label": "รวมทุกอาคาร", "count": int(len(today_df)), "kind": "total"})
    return cards


def render_home_mini_dashboard(
    df: pd.DataFrame,
    buildings: list[str],
    is_dark: bool,
    error_message: str | None = None,
) -> None:
    _render_styles(is_dark)
    if error_message:
        _render_html(
            '<div class="mini-dashboard-shell">'
            '<div class="mini-dashboard-error">ไม่สามารถโหลดข้อมูลสรุปวันนี้ได้</div>'
            '</div>'
        )
        return

    cards = get_today_building_counts(df, buildings)
    cards_html = "".join(_render_card(card) for card in cards)
    _render_html(
        '<div class="mini-dashboard-shell">'
        '<div class="mini-dashboard-title">สรุปยอดบันทึกวันนี้</div>'
        '<div class="mini-dashboard-scroll" aria-label="สรุปยอดบันทึกรถวันนี้">'
        '<div class="mini-dashboard-grid">'
        f"{cards_html}"
        "</div>"
        "</div>"
        "</div>"
    )


def _render_card(card: dict[str, object]) -> str:
    label = html.escape(str(card["label"]))
    count = html.escape(f"{int(card['count']):,}")
    kind = html.escape(str(card["kind"]))
    subtitle = "รายการวันนี้ทั้งหมด" if kind == "total" else "รายการวันนี้"
    icon = "∑" if kind == "total" else "▦"
    return (
        f'<div class="mini-stat-card mini-stat-card--{kind}">'
        '<div class="mini-stat-top">'
        f'<span class="mini-stat-icon">{icon}</span>'
        f'<span class="mini-stat-label">{label}</span>'
        "</div>"
        f'<div class="mini-stat-value">{count}</div>'
        f'<div class="mini-stat-subtitle">{subtitle}</div>'
        "</div>"
    )


def _render_html(markup: str) -> None:
    if hasattr(st, "html"):
        st.html(markup)
    else:
        st.markdown(markup, unsafe_allow_html=True)


def _render_styles(is_dark: bool) -> None:
    if is_dark:
        card_bg = "rgba(255,255,255,0.055)"
        card_border = "rgba(255,255,255,0.13)"
        text_primary = "#F8FAFC"
        text_secondary = "#B7C0CB"
        shell_title = "#E5EDF5"
        shadow = "none"
        total_border = "rgba(0, 209, 255, 0.36)"
        total_bg = "rgba(0, 209, 255, 0.08)"
    else:
        card_bg = "#FFFFFF"
        card_border = "#E2E8F0"
        text_primary = "#0F172A"
        text_secondary = "#64748B"
        shell_title = "#1F2937"
        shadow = "0 6px 18px rgba(15, 23, 42, 0.06)"
        total_border = "rgba(44, 83, 100, 0.36)"
        total_bg = "rgba(44, 83, 100, 0.06)"

    st.markdown(
        f"""
<style>
  .mini-dashboard-shell {{
    margin: -0.35rem 0 1.55rem;
  }}

  .mini-dashboard-title {{
    color: {shell_title};
    font-size: 0.98rem;
    font-weight: 600;
    margin: 0 0 0.55rem;
  }}

  .mini-dashboard-scroll {{
    width: 100%;
    overflow-x: auto;
    padding-bottom: 0.15rem;
  }}

  .mini-dashboard-grid {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    min-width: 680px;
    width: 100%;
  }}

  .mini-stat-card {{
    min-height: 112px;
    box-sizing: border-box;
    border-radius: 10px;
    border: 1px solid {card_border};
    background: {card_bg};
    box-shadow: {shadow};
    padding: 0.8rem 0.9rem;
  }}

  .mini-stat-card--total {{
    border-color: {total_border};
    background: {total_bg};
  }}

  .mini-stat-top {{
    display: flex;
    align-items: center;
    gap: 0.45rem;
    min-width: 0;
  }}

  .mini-stat-icon {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.35rem;
    height: 1.35rem;
    border-radius: 6px;
    color: #2c5364;
    background: rgba(44, 83, 100, 0.12);
    font-size: 0.86rem;
    flex: 0 0 auto;
  }}

  .mini-stat-label {{
    color: {text_secondary};
    font-size: clamp(0.74rem, 1.35vw, 0.88rem);
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}

  .mini-stat-value {{
    color: {text_primary};
    font-size: clamp(1.65rem, 3vw, 2.2rem);
    line-height: 1.05;
    font-weight: 700;
    margin-top: 0.55rem;
  }}

  .mini-stat-subtitle {{
    color: {text_secondary};
    font-size: 0.78rem;
    margin-top: 0.2rem;
  }}

  .mini-dashboard-error {{
    border: 1px solid rgba(239, 68, 68, 0.35);
    border-radius: 10px;
    padding: 0.85rem 1rem;
    color: #dc2626;
    background: rgba(239, 68, 68, 0.08);
  }}
</style>
""",
        unsafe_allow_html=True,
    )


def _first_five_buildings(buildings: list[str]) -> list[str | None]:
    cleaned = [str(building).strip() for building in buildings if str(building).strip()]
    selected: list[str | None] = cleaned[:5]
    while len(selected) < 5:
        selected.append(None)
    return selected


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lookup = {_normalize_column_name(column): column for column in df.columns}
    for candidate in candidates:
        found = lookup.get(_normalize_column_name(candidate))
        if found is not None:
            return found
    return None


def _normalize_column_name(value: object) -> str:
    return str(value).strip().lower().replace("_", "").replace("-", "").replace(" ", "")


def _parse_dates(series: pd.Series) -> pd.Series:
    as_text = series.astype(str).str.strip()
    parsed = pd.to_datetime(series, errors="coerce")
    slash_mask = as_text.str.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", na=False)
    if slash_mask.any():
        parsed.loc[slash_mask] = pd.to_datetime(
            as_text.loc[slash_mask],
            dayfirst=True,
            errors="coerce",
        )
    return pd.Series(parsed, index=series.index)
