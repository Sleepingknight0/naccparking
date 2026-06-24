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
    error_message: str | None = None,
) -> None:
    if error_message:
        _render_html(
            '<div class="mini-dashboard-shell">'
            '<div class="mini-dashboard-error">ไม่สามารถโหลดข้อมูลสรุปวันนี้ได้</div>'
            '</div>'
        )
        return

    cards = get_today_building_counts(df, buildings)
    _render_html(_build_dashboard_markup(cards))


def _build_dashboard_markup(cards: list[dict[str, object]]) -> str:
    cards_html = "".join(_render_card(card) for card in cards)
    return (
        '<div class="mini-dashboard-shell">'
        '<div class="mini-dashboard-title">สรุปยอดบันทึกวันนี้</div>'
        '<div class="mini-dashboard-wrap" aria-label="สรุปยอดบันทึกรถวันนี้">'
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
    subtitle = "รวมวันนี้" if kind == "total" else "รายการวันนี้"
    icon = "∑" if kind == "total" else "▦"
    return (
        f'<div class="mini-stat-card mini-stat-card--{kind}">'
        '<div class="mini-stat-top">'
        f'<span class="mini-stat-icon">{icon}</span>'
        f'<span class="mini-stat-title">{label}</span>'
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
