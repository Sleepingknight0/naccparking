from __future__ import annotations

import streamlit as st

from dashboard import components, overview, period_analysis, raw_data, vehicle_analysis
from dashboard.data_service import clear_dashboard_cache, get_dashboard_data
from dashboard.styles import apply_dashboard_styles


st.set_page_config(
    page_title="Dashboard รถค้างอาคาร",
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

st.sidebar.page_link("app_parking.py", label="กลับหน้าบันทึกข้อมูล")
st.sidebar.markdown("---")
if st.sidebar.button("Refresh data", use_container_width=True):
    clear_dashboard_cache()
    st.rerun()
st.sidebar.markdown("---")
selected_page = st.sidebar.radio(
    "Dashboard",
    [
        "ภาพรวม Dashboard",
        "วิเคราะห์ตามช่วงเวลา",
        "วิเคราะห์รายคัน / ค้างคืน",
        "ตารางข้อมูลดิบ / Export",
    ],
)

st.markdown('<div class="dashboard-shell">', unsafe_allow_html=True)
result = get_dashboard_data()
components.render_hero(
    "Dashboard รถค้างอาคาร",
    "ภาพรวมข้อมูลรถค้างอาคารจาก Google Sheets",
    result.loaded_at,
)

if result.error:
    components.render_error(result.error)
elif result.prepared.empty:
    components.render_empty("ยังไม่มีข้อมูลที่พร้อมแสดงผล หรือวันที่ใน Sheet parse ไม่ได้")
else:
    if selected_page == "ภาพรวม Dashboard":
        overview.render(result.prepared)
    elif selected_page == "วิเคราะห์ตามช่วงเวลา":
        period_analysis.render(result.prepared)
    elif selected_page == "วิเคราะห์รายคัน / ค้างคืน":
        vehicle_analysis.render(result.prepared)
    else:
        raw_data.render(result.prepared)

st.markdown("</div>", unsafe_allow_html=True)
