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
    st.line_chart(daily.set_index(DATE_COL), height=260)

    left, right = st.columns(2)
    with left:
        components.section_title("Top 10 อาคารที่พบรถค้าง")
        top_buildings = top_counts(filtered, BUILDING_COL, 10)
        if top_buildings.empty:
            components.render_empty()
        else:
            st.bar_chart(top_buildings.set_index(BUILDING_COL), height=280)
    with right:
        components.section_title("Top 10 จังหวัด")
        top_provinces = top_counts(filtered, PROVINCE_COL, 10)
        if top_provinces.empty:
            components.render_empty()
        else:
            st.bar_chart(top_provinces.set_index(PROVINCE_COL), height=280)

    components.section_title("Matrix รายวัน x อาคาร")
    matrix = building_day_matrix(filtered)
    if matrix.empty:
        components.render_empty("ยังไม่มีข้อมูลพอสำหรับ matrix")
    else:
        st.dataframe(matrix, use_container_width=True)

    components.section_title("รายการล่าสุด 20 รายการ")
    latest = filtered.sort_values(DATE_COL, ascending=False).head(20)
    st.dataframe(prepare_display_dataframe(latest), use_container_width=True, hide_index=True)
