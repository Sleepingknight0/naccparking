from __future__ import annotations

import streamlit as st

from dashboard import components
from dashboard.data_service import BUILDING_COL, DATE_COL, PROVINCE_COL, clear_dashboard_cache
from dashboard.display import prepare_display_dataframe
from dashboard.metrics import building_day_matrix, daily_counts, filter_dataframe, top_counts


def render(df) -> None:
    filters = components.render_filter_bar(df, "overview")
    if filters.get("refresh"):
        clear_dashboard_cache()
        st.rerun()

    filtered = filter_dataframe(
        df,
        buildings=filters["buildings"],
        provinces=filters["provinces"],
        year=filters["year"],
        month=filters["month"],
        date_range=filters["date_range"],
    )

    if filtered.empty:
        components.render_empty()
        return

    components.render_kpi_cards(filtered)

    components.section_title("จำนวนรายการตามวัน")
    daily = daily_counts(filtered)
    components.render_daily_counts_chart(daily, height=280)

    left, right = st.columns(2)
    with left:
        components.section_title("Top 10 อาคารที่พบรถค้าง")
        top_buildings = top_counts(filtered, BUILDING_COL, 10)
        components.render_horizontal_bar_chart(top_buildings, BUILDING_COL, height=280)
    with right:
        components.section_title("Top 10 จังหวัด")
        top_provinces = top_counts(filtered, PROVINCE_COL, 10)
        components.render_horizontal_bar_chart(top_provinces, PROVINCE_COL, height=280)

    components.section_title("Matrix รายวัน x อาคาร")
    matrix = building_day_matrix(filtered)
    if matrix.empty:
        components.render_empty("ยังไม่มีข้อมูลพอสำหรับ matrix")
    else:
        matrix_display = matrix.copy()
        matrix_display.index = [
            value.strftime("%d/%m/%Y") if hasattr(value, "strftime") else str(value)
            for value in matrix_display.index
        ]
        st.dataframe(matrix_display, use_container_width=True, height=360)

    components.section_title("รายการล่าสุด 20 รายการ")
    latest = filtered.sort_values(DATE_COL, ascending=False).head(20)
    st.dataframe(prepare_display_dataframe(latest), use_container_width=True, hide_index=True)
