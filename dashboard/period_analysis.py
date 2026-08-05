from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from dashboard import components
from dashboard.data_service import BUILDING_COL, DATE_COL, NORMALIZED_PLATE_COL, PROVINCE_COL
from dashboard.display import prepare_display_dataframe
from dashboard.metrics import (
    build_week_options,
    daily_counts,
    filter_dataframe,
    summarize_by_building,
    top_counts,
)


def render(df: pd.DataFrame) -> None:
    mode_options = ["รายวัน", "รายสัปดาห์", "รายเดือน"]
    if hasattr(st, "segmented_control"):
        mode = st.segmented_control(
            "เลือกรูปแบบการวิเคราะห์",
            options=mode_options,
            default="รายวัน",
            key="period_mode",
        )
    else:
        mode = st.radio(
            "เลือกรูปแบบการวิเคราะห์",
            options=mode_options,
            horizontal=True,
            key="period_mode",
        )

    if mode == "รายวัน":
        _render_daily(df)
    elif mode == "รายสัปดาห์":
        _render_weekly(df)
    else:
        _render_monthly(df)


def _render_daily(df: pd.DataFrame) -> None:
    components.section_title("วิเคราะห์รายวัน")
    year, month = components.month_year_controls(df, "daily")
    month_df = filter_dataframe(df, year=year, month=month)
    if month_df.empty:
        components.render_empty()
        return

    selected_date = st.date_input(
        "เลือกวันที่",
        value=month_df[DATE_COL].max(),
        min_value=date(year, month, 1),
        max_value=date(year, month, pd.Period(f"{year}-{month:02d}").days_in_month),
        key="daily_selected_date",
    )
    day_df = filter_dataframe(month_df, date_range=(selected_date, selected_date))
    if day_df.empty:
        components.render_empty()
        return

    components.render_kpi_cards(day_df)
    left, right = st.columns(2)
    with left:
        components.section_title("จำนวนตามอาคาร")
        components.render_horizontal_bar_chart(top_counts(day_df, BUILDING_COL, 20), BUILDING_COL, height=280)
    with right:
        if "เวลา" in day_df.columns and day_df["เวลา"].fillna("").astype(str).str.strip().ne("").any():
            components.section_title("จำนวนตามช่วงเวลา")
            time_counts = day_df["เวลา"].fillna("ไม่ระบุ").replace("", "ไม่ระบุ").value_counts().sort_index()
            st.bar_chart(time_counts, height=280)
        else:
            components.section_title("Top จังหวัด")
            components.render_horizontal_bar_chart(top_counts(day_df, PROVINCE_COL, 10), PROVINCE_COL, height=280)

    components.section_title("รายการรถทั้งหมดของวันนั้น")
    st.dataframe(prepare_display_dataframe(day_df), use_container_width=True, hide_index=True)


def _render_weekly(df: pd.DataFrame) -> None:
    components.section_title("วิเคราะห์รายสัปดาห์")
    year, month = components.month_year_controls(df, "weekly")
    week_options = build_week_options(year, month)
    selected_week = st.selectbox(
        "เลือกสัปดาห์",
        week_options,
        format_func=lambda item: item["label"],
        key="weekly_selected_week",
    )
    st.caption(f"ช่วงวันที่: {selected_week['start']:%d/%m/%Y} - {selected_week['end']:%d/%m/%Y}")

    week_df = filter_dataframe(
        df,
        date_range=(selected_week["start"], selected_week["end"]),
    )
    if week_df.empty:
        components.render_empty()
        return

    components.render_kpi_cards(week_df)
    components.section_title("Trend รายวันในสัปดาห์")
    components.render_daily_counts_chart(daily_counts(week_df), height=280)

    col_building, col_province, col_plate = st.columns(3)
    with col_building:
        components.section_title("Top อาคาร")
        st.dataframe(top_counts(week_df, BUILDING_COL, 10), use_container_width=True, hide_index=True)
    with col_province:
        components.section_title("Top จังหวัด")
        st.dataframe(top_counts(week_df, PROVINCE_COL, 10), use_container_width=True, hide_index=True)
    with col_plate:
        components.section_title("ทะเบียนที่พบซ้ำ")
        if NORMALIZED_PLATE_COL not in week_df.columns:
            components.render_empty("ไม่มีข้อมูลทะเบียนสำหรับสรุป")
        else:
            repeats = (
                week_df.groupby(NORMALIZED_PLATE_COL)
                .size()
                .reset_index(name="จำนวนครั้ง")
                .sort_values("จำนวนครั้ง", ascending=False)
                .head(10)
                .rename(columns={NORMALIZED_PLATE_COL: "ทะเบียนรถมาตรฐาน"})
            )
            st.dataframe(repeats, use_container_width=True, hide_index=True)


def _render_monthly(df: pd.DataFrame) -> None:
    components.section_title("วิเคราะห์รายเดือน")
    year, month = components.month_year_controls(df, "monthly")
    month_df = filter_dataframe(df, year=year, month=month)
    if month_df.empty:
        components.render_empty()
        return

    components.render_kpi_cards(month_df)
    components.section_title("Trend รายวันทั้งเดือน")
    components.render_daily_counts_chart(daily_counts(month_df), height=280)

    left, right = st.columns(2)
    with left:
        components.section_title("Top อาคาร")
        components.render_horizontal_bar_chart(top_counts(month_df, BUILDING_COL, 10), BUILDING_COL, height=280)
    with right:
        components.section_title("Top จังหวัด")
        components.render_horizontal_bar_chart(top_counts(month_df, PROVINCE_COL, 10), PROVINCE_COL, height=280)

    components.section_title("ตารางสรุปตามอาคาร")
    summary_df = summarize_by_building(month_df)
    if summary_df.empty:
        components.render_empty("ไม่พบข้อมูลสำหรับสรุปตามอาคาร")
    else:
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
