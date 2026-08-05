from __future__ import annotations

import streamlit as st

from dashboard import components, overview, period_analysis, raw_data, vehicle_analysis
from dashboard.data_service import clear_dashboard_cache, get_dashboard_data
from dashboard.styles import apply_dashboard_styles
from dashboard.theme import init_theme_state, is_dark_theme


st.set_page_config(
    page_title="แดชบอร์ดรถค้างอาคาร",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


init_theme_state()
apply_dashboard_styles(is_dark_theme())


DASHBOARD_SECTIONS = {
    "overview": "› ภาพรวมแดชบอร์ด",
    "period": "› วิเคราะห์ตามช่วงเวลา",
    "vehicle": "› วิเคราะห์รายคัน / ค้างคืน",
    "raw": "› ตารางข้อมูลดิบ / ส่งออก",
}


if "dashboard_section" not in st.session_state:
    st.session_state.dashboard_section = "overview"


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
st.sidebar.markdown("**เมนูแดชบอร์ด**")
for section_key, section_label in DASHBOARD_SECTIONS.items():
    is_active = st.session_state.dashboard_section == section_key
    if st.sidebar.button(
        section_label,
        key=f"dashboard_nav_{section_key}",
        use_container_width=True,
        type="primary" if is_active else "secondary",
    ):
        st.session_state.dashboard_section = section_key
        st.rerun()

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
    selected_section = st.session_state.dashboard_section
    if selected_section == "overview":
        _render_section("ไม่สามารถแสดงผลภาพรวมแดชบอร์ดได้", overview.render, result.prepared)
    elif selected_section == "period":
        _render_section("ไม่สามารถแสดงผลวิเคราะห์ตามช่วงเวลาได้", period_analysis.render, result.prepared)
    elif selected_section == "vehicle":
        _render_section("ไม่สามารถแสดงผลวิเคราะห์รายคันได้", vehicle_analysis.render, result.prepared)
    else:
        _render_section("ไม่สามารถแสดงผลตารางข้อมูลดิบได้", raw_data.render, result.prepared)
