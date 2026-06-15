from __future__ import annotations

import streamlit as st

from dashboard import components, overview, period_analysis, raw_data, vehicle_analysis
from dashboard.data_service import clear_dashboard_cache, get_dashboard_data
from dashboard.styles import apply_dashboard_styles


st.set_page_config(
    page_title="แดชบอร์ดรถค้างอาคาร",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _is_dark_theme() -> bool:
    try:
        return st.get_option("theme.base") == "dark"
    except Exception:
        return True


apply_dashboard_styles(_is_dark_theme())


def _render_section(error_message: str, renderer, data) -> None:
    try:
        renderer(data)
    except Exception as exc:
        st.error(error_message)
        with st.expander("รายละเอียดสำหรับผู้ดูแลระบบ"):
            st.exception(exc)


st.sidebar.page_link("app_parking.py", label="› กลับหน้าบันทึกข้อมูล")
st.sidebar.markdown("---")
if st.sidebar.button("รีเฟรชข้อมูล", use_container_width=True):
    clear_dashboard_cache()
    st.rerun()
st.sidebar.markdown("---")
selected_page = st.sidebar.radio(
    "เมนูแดชบอร์ด",
    [
        "ภาพรวมแดชบอร์ด",
        "วิเคราะห์ตามช่วงเวลา",
        "วิเคราะห์รายคัน / ค้างคืน",
        "ตารางข้อมูลดิบ / ส่งออก",
    ],
)

result = get_dashboard_data()
components.render_hero(
    "แดชบอร์ดรถค้างอาคาร",
    "ภาพรวมข้อมูลรถค้างอาคารจาก Google Sheets",
    result.loaded_at,
)

if result.error:
    components.render_error(result.error)
elif result.prepared.empty:
    components.render_empty("ยังไม่มีข้อมูลที่พร้อมแสดงผล หรือวันที่ใน Sheet parse ไม่ได้")
else:
    if selected_page == "ภาพรวมแดชบอร์ด":
        _render_section("ไม่สามารถแสดงผลภาพรวมแดชบอร์ดได้", overview.render, result.prepared)
    elif selected_page == "วิเคราะห์ตามช่วงเวลา":
        _render_section("ไม่สามารถแสดงผลวิเคราะห์ตามช่วงเวลาได้", period_analysis.render, result.prepared)
    elif selected_page == "วิเคราะห์รายคัน / ค้างคืน":
        _render_section("ไม่สามารถแสดงผลวิเคราะห์รายคันได้", vehicle_analysis.render, result.prepared)
    else:
        _render_section("ไม่สามารถแสดงผลตารางข้อมูลดิบได้", raw_data.render, result.prepared)
