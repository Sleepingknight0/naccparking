from __future__ import annotations

import html
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.data_service import BUILDING_COL, DATE_COL, PROVINCE_COL
from dashboard.metrics import THAI_MONTH_BY_NUMBER, compute_kpis, month_options
from dashboard.theme import is_dark_theme


COUNT_COL = "จำนวนรายการ"
DISPLAY_DATE_COL = "วันที่"


def render_hero(title: str, subtitle: str, loaded_at) -> None:
    synced = "ยังไม่ได้ sync"
    if loaded_at is not None:
        synced = loaded_at.strftime("%d/%m/%Y %H:%M:%S %Z")
    st.markdown(
        f"""
<div class="dash-hero">
    <h1>{title}</h1>
    <p>{subtitle}</p>
    <div class="dash-sync">Sync ล่าสุด: {synced}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_error(message: str) -> None:
    st.markdown(
        '<div class="dash-error">ไม่สามารถโหลดข้อมูลแดชบอร์ดได้ กรุณาตรวจสอบการเชื่อมต่อ Google Sheets หรือสิทธิ์การเข้าถึง</div>',
        unsafe_allow_html=True,
    )
    with st.expander("รายละเอียดสำหรับผู้ดูแลระบบ"):
        st.code(str(message))


def render_empty(message: str = "ไม่พบข้อมูลในช่วงเวลานี้") -> None:
    st.markdown(f'<div class="dash-empty">{message}</div>', unsafe_allow_html=True)


def section_title(title: str) -> None:
    st.markdown(f'<div class="dash-section-title">{title}</div>', unsafe_allow_html=True)


def render_kpi_cards(df: pd.DataFrame) -> None:
    kpis = compute_kpis(df)
    cards = [
        ("▦", "จำนวนรายการทั้งหมด", f"{kpis['total_records']:,}", "รายการหลังกรอง"),
        ("▦", "ทะเบียนรถไม่ซ้ำ", f"{kpis['unique_vehicles']:,}", "นับจากทะเบียนมาตรฐาน"),
        ("▦", "อาคารที่มีข้อมูล", f"{kpis['building_count']:,}", "อาคารไม่ซ้ำ"),
        ("▦", "รายการเข้าข่ายค้างคืน", f"{kpis['overnight_count']:,}", f"{kpis['overnight_vehicle_count']:,} ทะเบียน"),
        (
            "▦",
            "วันที่มีรถค้างมากที่สุด",
            _format_date(kpis["busiest_day"]),
            f"{kpis['busiest_day_count']:,} รายการ",
        ),
        (
            "∑",
            "อาคารที่พบมากที่สุด",
            str(kpis["top_building"]),
            f"{kpis['top_building_count']:,} รายการ",
        ),
    ]
    cards_html = "".join(
        _kpi_card_html(icon, label, value, note)
        for icon, label, value, note in cards
    )
    st.markdown(f'<div class="dash-kpi-grid">{cards_html}</div>', unsafe_allow_html=True)


def render_daily_counts_chart(daily_df: pd.DataFrame, height: int = 280) -> None:
    if daily_df is None or daily_df.empty or DATE_COL not in daily_df.columns:
        render_empty("ไม่มีข้อมูลสำหรับแสดงกราฟนี้")
        return

    chart_df = daily_df.copy()
    chart_df[DISPLAY_DATE_COL] = pd.to_datetime(chart_df[DATE_COL], errors="coerce").dt.strftime("%d/%m/%Y")
    chart_df = chart_df.dropna(subset=[DISPLAY_DATE_COL])
    if chart_df.empty:
        render_empty("ไม่มีข้อมูลสำหรับแสดงกราฟนี้")
        return

    count_col = _count_column(chart_df)
    chart = (
        alt.Chart(chart_df)
        .mark_line(point=True, interpolate="monotone", color=_chart_accent())
        .encode(
            x=alt.X(
                f"{DISPLAY_DATE_COL}:N",
                title="วันที่",
                sort=chart_df[DISPLAY_DATE_COL].tolist(),
                axis=alt.Axis(labelAngle=-25, labelOverlap=False),
            ),
            y=alt.Y(f"{count_col}:Q", title="จำนวนรายการ", axis=alt.Axis(format="d")),
            tooltip=[
                alt.Tooltip(f"{DISPLAY_DATE_COL}:N", title="วันที่"),
                alt.Tooltip(f"{count_col}:Q", title="จำนวนรายการ", format=","),
            ],
        )
        .properties(height=height)
        .configure_axis(labelColor=_chart_text(), titleColor=_chart_text(), gridColor=_chart_grid())
        .configure_view(stroke=None)
    )
    st.altair_chart(chart, use_container_width=True)


def render_horizontal_bar_chart(
    chart_df: pd.DataFrame,
    category_col: str,
    height: int = 300,
) -> None:
    if chart_df is None or chart_df.empty or category_col not in chart_df.columns:
        render_empty("ไม่มีข้อมูลสำหรับแสดงกราฟนี้")
        return

    plot_df = chart_df.copy()
    count_col = _count_column(plot_df)
    plot_df[category_col] = plot_df[category_col].fillna("ไม่ระบุ").replace("", "ไม่ระบุ").astype(str)
    plot_df[count_col] = pd.to_numeric(plot_df[count_col], errors="coerce").fillna(0)
    plot_df = plot_df.sort_values(count_col, ascending=False)
    if plot_df.empty:
        render_empty("ไม่มีข้อมูลสำหรับแสดงกราฟนี้")
        return

    chart = (
        alt.Chart(plot_df)
        .mark_bar(color=_chart_accent())
        .encode(
            x=alt.X(f"{count_col}:Q", title="จำนวนรายการ", axis=alt.Axis(format="d")),
            y=alt.Y(
                f"{category_col}:N",
                title=None,
                sort=plot_df[category_col].tolist(),
                axis=alt.Axis(labelLimit=180, labelOverlap=False),
            ),
            tooltip=[
                alt.Tooltip(f"{category_col}:N", title=category_col),
                alt.Tooltip(f"{count_col}:Q", title="จำนวนรายการ", format=","),
            ],
        )
        .properties(height=max(height, 28 * len(plot_df)))
        .configure_axis(labelColor=_chart_text(), titleColor=_chart_text(), gridColor=_chart_grid())
        .configure_view(stroke=None)
    )
    st.altair_chart(chart, use_container_width=True)


def render_filter_bar(df: pd.DataFrame, key_prefix: str) -> dict[str, object]:
    if df.empty:
        return {"buildings": [], "provinces": [], "year": None, "month": None, "date_range": None}

    building_options = sorted(df[BUILDING_COL].dropna().astype(str).unique())
    province_options = sorted(df[PROVINCE_COL].dropna().astype(str).unique())
    months = month_options(df)
    month_labels = ["ทั้งหมด"] + [label for _, _, label in months]

    st.markdown('<div class="dash-filter-title">ตัวกรองข้อมูล</div>', unsafe_allow_html=True)
    col_building, col_province, col_month, col_range, col_refresh = st.columns([1.25, 1.1, 1, 1.35, 0.75])
    with col_building:
        buildings = st.multiselect("อาคาร", building_options, key=f"{key_prefix}_buildings")
    with col_province:
        provinces = st.multiselect("จังหวัด", province_options, key=f"{key_prefix}_provinces")
    with col_month:
        selected_month_label = st.selectbox("เดือน", month_labels, key=f"{key_prefix}_month")
    with col_range:
        min_date = df[DATE_COL].min()
        max_date = df[DATE_COL].max()
        selected_range = st.date_input(
            "ช่วงวันที่",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key=f"{key_prefix}_date_range",
        )
    with col_refresh:
        st.write("")
        refresh = st.button("รีเฟรช", key=f"{key_prefix}_refresh", use_container_width=True)

    selected_year = None
    selected_month = None
    if selected_month_label != "ทั้งหมด":
        selected_year, selected_month, _ = months[month_labels.index(selected_month_label) - 1]

    if isinstance(selected_range, tuple) and len(selected_range) == 2:
        date_range = selected_range
    else:
        date_range = (selected_range, selected_range)

    return {
        "buildings": buildings,
        "provinces": provinces,
        "year": selected_year,
        "month": selected_month,
        "date_range": date_range,
        "refresh": refresh,
    }


def month_year_controls(df: pd.DataFrame, key_prefix: str) -> tuple[int, int]:
    months = month_options(df)
    year_values = sorted({year for year, _, _ in months}, reverse=True)
    if not year_values:
        today = date.today()
        year_values = [today.year]
    current_month = date.today().month

    col_year, col_month = st.columns(2)
    with col_year:
        year = st.selectbox("เลือกปี", year_values, key=f"{key_prefix}_year")
    month_numbers = [month for y, month, _ in months if y == year] or list(range(1, 13))
    if current_month in month_numbers:
        default_index = month_numbers.index(current_month)
    else:
        default_index = 0
    with col_month:
        month = st.selectbox(
            "เลือกเดือน",
            month_numbers,
            format_func=lambda value: THAI_MONTH_BY_NUMBER.get(value, str(value)),
            index=default_index,
            key=f"{key_prefix}_month_select",
        )
    return year, month


def _format_date(value: object) -> str:
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return "-" if value is None else str(value)


def _kpi_card_html(icon: str, label: str, value: str, note: str) -> str:
    return (
        '<div class="dash-kpi-card">'
        '<div class="dash-kpi-top">'
        f'<span class="dash-kpi-icon">{html.escape(icon)}</span>'
        f'<span class="dash-kpi-title">{html.escape(label)}</span>'
        "</div>"
        f'<div class="dash-kpi-big">{html.escape(value)}</div>'
        f'<div class="dash-kpi-caption">{html.escape(note)}</div>'
        "</div>"
    )


def _count_column(df: pd.DataFrame) -> str:
    if COUNT_COL in df.columns:
        return COUNT_COL
    for column in df.columns:
        if column != DATE_COL:
            return column
    return COUNT_COL


def _chart_text() -> str:
    return "#F4F7FA" if is_dark_theme() else "#0F172A"


def _chart_grid() -> str:
    return "rgba(167,176,188,0.18)" if is_dark_theme() else "rgba(82,97,115,0.18)"


def _chart_accent() -> str:
    return "#00A7C8" if is_dark_theme() else "#2C5364"
