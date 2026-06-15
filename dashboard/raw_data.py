from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard import components
from dashboard.data_service import DERIVED_COLUMNS, clear_dashboard_cache, to_csv_bytes, to_excel_bytes
from dashboard.metrics import filter_dataframe


def render(df: pd.DataFrame) -> None:
    filters = components.render_filter_bar(df, "raw")
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

    search = st.text_input("ค้นหาในตาราง", placeholder="ค้นทะเบียน อาคาร จังหวัด หรือข้อความอื่น", key="raw_search")
    filtered = filter_dataframe(filtered, search_text=search)
    show_derived = st.toggle("แสดง column ที่ระบบคำนวณเพิ่ม", value=False, key="raw_show_derived")

    display_df = _display_columns(filtered, show_derived)
    st.caption(f"จำนวน row หลัง filter: {len(display_df):,}")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    col_csv, col_excel = st.columns(2)
    with col_csv:
        st.download_button(
            "Download CSV",
            data=to_csv_bytes(display_df),
            file_name="naccparking-dashboard.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_excel:
        try:
            excel_bytes = to_excel_bytes(display_df)
            st.download_button(
                "Download Excel",
                data=excel_bytes,
                file_name="naccparking-dashboard.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as exc:
            st.warning(f"ยังไม่สามารถสร้าง Excel ได้: {exc}")


def _display_columns(df: pd.DataFrame, show_derived: bool) -> pd.DataFrame:
    if show_derived:
        return df
    derived_set = set(DERIVED_COLUMNS + ["next_gap_days"])
    columns = [column for column in df.columns if column not in derived_set]
    return df[columns]
