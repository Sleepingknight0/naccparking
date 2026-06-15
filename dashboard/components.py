from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from dashboard.data_service import BUILDING_COL, DATE_COL, PROVINCE_COL
from dashboard.metrics import THAI_MONTH_BY_NUMBER, compute_kpis, month_options


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
        f'<div class="dash-error">ไม่สามารถโหลดข้อมูลแดชบอร์ดได้: {message}</div>',
        unsafe_allow_html=True,
    )


def render_empty(message: str = "ไม่พบข้อมูลในช่วงเวลานี้") -> None:
    st.markdown(f'<div class="dash-empty">{message}</div>', unsafe_allow_html=True)


def section_title(title: str) -> None:
    st.markdown(f'<div class="dash-section-title">{title}</div>', unsafe_allow_html=True)


def render_kpi_cards(df: pd.DataFrame) -> None:
    kpis = compute_kpis(df)
    cards = [
        ("จำนวนรายการทั้งหมด", f"{kpis['total_records']:,}", "รายการหลังกรอง"),
        ("ทะเบียนรถไม่ซ้ำ", f"{kpis['unique_vehicles']:,}", "นับจากทะเบียนมาตรฐาน"),
        ("อาคารที่มีข้อมูล", f"{kpis['building_count']:,}", "อาคารไม่ซ้ำ"),
        ("รายการเข้าข่ายค้างคืน", f"{kpis['overnight_count']:,}", f"{kpis['overnight_vehicle_count']:,} ทะเบียน"),
        (
            "วันที่มีรถค้างมากที่สุด",
            _format_date(kpis["busiest_day"]),
            f"{kpis['busiest_day_count']:,} รายการ",
        ),
        (
            "อาคารที่พบมากที่สุด",
            str(kpis["top_building"]),
            f"{kpis['top_building_count']:,} รายการ",
        ),
    ]
    columns = st.columns(3)
    for index, (label, value, note) in enumerate(cards):
        with columns[index % 3]:
            st.markdown(
                f"""
<div class="dash-card">
    <div class="dash-kpi-label">{label}</div>
    <div class="dash-kpi-value">{value}</div>
    <div class="dash-kpi-note">{note}</div>
</div>
""",
                unsafe_allow_html=True,
            )


def render_filter_bar(df: pd.DataFrame, key_prefix: str) -> dict[str, object]:
    if df.empty:
        return {"buildings": [], "provinces": [], "year": None, "month": None, "date_range": None}

    building_options = sorted(df[BUILDING_COL].dropna().astype(str).unique())
    province_options = sorted(df[PROVINCE_COL].dropna().astype(str).unique())
    months = month_options(df)
    month_labels = ["ทั้งหมด"] + [label for _, _, label in months]

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
