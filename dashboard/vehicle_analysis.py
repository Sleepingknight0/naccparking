from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard import components
from dashboard.data_service import (
    BUILDING_COL,
    DATE_COL,
    OVERNIGHT_COL,
    OVERNIGHT_REASON_COL,
    PLATE_COL,
    PROVINCE_COL,
)
from dashboard.metrics import vehicle_options, vehicle_profile


def render(df: pd.DataFrame) -> None:
    components.section_title("ค้นทะเบียนรถ")
    query = st.text_input("ค้นหาทะเบียนรถ", placeholder="เช่น กก หรือ 1234", key="vehicle_query")
    options = vehicle_options(df, query)

    if not query.strip():
        components.render_empty("พิมพ์บางส่วนของทะเบียนรถเพื่อค้นหา")
        return
    if not options:
        components.render_empty("ไม่พบทะเบียนรถที่ตรงกับคำค้น")
        return

    selected_plate = st.selectbox("เลือกทะเบียนจากผลลัพธ์", options, key="vehicle_selected_plate")
    profile, history = vehicle_profile(df, selected_plate)
    if not profile:
        components.render_empty("ไม่พบประวัติของทะเบียนนี้")
        return

    _render_profile(profile)
    _render_timeline(history)

    components.section_title("ประวัติการจอด")
    st.dataframe(history, use_container_width=True, hide_index=True)

    components.section_title("วันที่เข้าข่ายจอดค้าง")
    overnight = history[history[OVERNIGHT_COL] == True]
    if overnight.empty:
        components.render_empty("ยังไม่พบวันที่เข้าข่ายจอดค้าง")
    else:
        columns = [DATE_COL, BUILDING_COL, PROVINCE_COL, OVERNIGHT_REASON_COL]
        st.dataframe(overnight[columns], use_container_width=True, hide_index=True)


def _render_profile(profile: dict[str, object]) -> None:
    cards = [
        ("ทะเบียนรถ", profile["plate"], profile["province"]),
        ("จำนวนครั้งที่พบ", f"{profile['total_seen']:,}", "รายการทั้งหมด"),
        ("อาคารที่พบบ่อยสุด", profile["top_building"], "จากประวัติทั้งหมด"),
        ("พบครั้งแรก", _format_date(profile["first_seen"]), f"ล่าสุด {_format_date(profile['last_seen'])}"),
        ("จำนวนวันที่ค้างคืน", f"{profile['overnight_days']:,}", "นับจากวันที่เข้าข่าย"),
    ]
    columns = st.columns(5)
    for index, (label, value, note) in enumerate(cards):
        with columns[index]:
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


def _render_timeline(history: pd.DataFrame) -> None:
    components.section_title("Timeline วันที่พบ")
    latest = history.sort_values(DATE_COL, ascending=False).head(30)
    for _, row in latest.iterrows():
        reason = row.get(OVERNIGHT_REASON_COL, "-")
        marker = "เข้าข่ายค้างต่อเนื่อง" if row.get(OVERNIGHT_COL) else "รายการพบปกติ"
        st.markdown(
            f"""
<div class="dash-timeline-item">
    <strong>{_format_date(row[DATE_COL])}</strong> · {row.get(PLATE_COL, "")}
    <div class="dash-timeline-meta">{row.get(BUILDING_COL, "-")} · {row.get(PROVINCE_COL, "-")} · {marker}</div>
    <div class="dash-timeline-meta">{reason}</div>
</div>
""",
            unsafe_allow_html=True,
        )


def _format_date(value: object) -> str:
    return value.strftime("%d/%m/%Y") if hasattr(value, "strftime") else str(value)

