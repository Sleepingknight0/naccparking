from __future__ import annotations

import calendar
from datetime import date, timedelta

import pandas as pd

from dashboard.data_service import (
    BUILDING_COL,
    DATE_COL,
    NORMALIZED_PLATE_COL,
    OVERNIGHT_COL,
    PLATE_COL,
    PROVINCE_COL,
)


THAI_MONTHS = [
    (1, "มกราคม"),
    (2, "กุมภาพันธ์"),
    (3, "มีนาคม"),
    (4, "เมษายน"),
    (5, "พฤษภาคม"),
    (6, "มิถุนายน"),
    (7, "กรกฎาคม"),
    (8, "สิงหาคม"),
    (9, "กันยายน"),
    (10, "ตุลาคม"),
    (11, "พฤศจิกายน"),
    (12, "ธันวาคม"),
]
THAI_MONTH_BY_NUMBER = dict(THAI_MONTHS)


def filter_dataframe(
    df: pd.DataFrame,
    buildings: list[str] | None = None,
    provinces: list[str] | None = None,
    year: int | None = None,
    month: int | None = None,
    date_range: tuple[date, date] | None = None,
    search_text: str | None = None,
) -> pd.DataFrame:
    filtered = df.copy()
    if filtered.empty:
        return filtered

    if buildings:
        filtered = filtered[filtered[BUILDING_COL].isin(buildings)]
    if provinces:
        filtered = filtered[filtered[PROVINCE_COL].isin(provinces)]
    if year:
        filtered = filtered[pd.to_datetime(filtered[DATE_COL]).dt.year == year]
    if month:
        filtered = filtered[pd.to_datetime(filtered[DATE_COL]).dt.month == month]
    if date_range:
        start, end = date_range
        filtered = filtered[(filtered[DATE_COL] >= start) & (filtered[DATE_COL] <= end)]
    if search_text:
        query = search_text.strip().lower()
        if query:
            searchable = filtered.fillna("").astype(str).agg(" ".join, axis=1).str.lower()
            filtered = filtered[searchable.str.contains(query, regex=False)]

    return filtered.reset_index(drop=True)


def compute_kpis(df: pd.DataFrame) -> dict[str, object]:
    if df.empty:
        return {
            "total_records": 0,
            "unique_vehicles": 0,
            "building_count": 0,
            "overnight_count": 0,
            "overnight_vehicle_count": 0,
            "busiest_day": None,
            "busiest_day_count": 0,
            "top_building": "-",
            "top_building_count": 0,
        }

    day_counts = df[DATE_COL].value_counts()
    building_counts = df[BUILDING_COL].replace("", "ไม่ระบุอาคาร").value_counts()
    overnight_df = df[df[OVERNIGHT_COL] == True]
    return {
        "total_records": int(len(df)),
        "unique_vehicles": int(df[NORMALIZED_PLATE_COL].nunique()),
        "building_count": int(df[BUILDING_COL].replace("", pd.NA).dropna().nunique()),
        "overnight_count": int(len(overnight_df)),
        "overnight_vehicle_count": int(overnight_df[NORMALIZED_PLATE_COL].nunique()),
        "busiest_day": day_counts.index[0] if not day_counts.empty else None,
        "busiest_day_count": int(day_counts.iloc[0]) if not day_counts.empty else 0,
        "top_building": building_counts.index[0] if not building_counts.empty else "-",
        "top_building_count": int(building_counts.iloc[0]) if not building_counts.empty else 0,
    }


def daily_counts(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[DATE_COL, "จำนวนรายการ"])
    counts = (
        df.groupby(DATE_COL)
        .size()
        .reset_index(name="จำนวนรายการ")
        .sort_values(DATE_COL)
    )
    return counts


def top_counts(df: pd.DataFrame, column: str, limit: int = 10) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return pd.DataFrame(columns=[column, "จำนวนรายการ"])
    counts = (
        df[column]
        .fillna("ไม่ระบุ")
        .replace("", "ไม่ระบุ")
        .value_counts()
        .head(limit)
        .rename_axis(column)
        .reset_index(name="จำนวนรายการ")
    )
    return counts


def building_day_matrix(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    matrix = pd.pivot_table(
        df,
        index=DATE_COL,
        columns=BUILDING_COL,
        values=PLATE_COL,
        aggfunc="count",
        fill_value=0,
    ).sort_index()
    return matrix


def summarize_by_building(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[BUILDING_COL, "จำนวนรายการ", "ทะเบียนไม่ซ้ำ", "รถค้างคืน"])
    summary = (
        df.groupby(BUILDING_COL)
        .agg(
            จำนวนรายการ=(PLATE_COL, "count"),
            ทะเบียนไม่ซ้ำ=(NORMALIZED_PLATE_COL, "nunique"),
            รถค้างคืน=(OVERNIGHT_COL, "sum"),
        )
        .reset_index()
        .sort_values("จำนวนรายการ", ascending=False)
    )
    summary["รถค้างคืน"] = summary["รถค้างคืน"].astype(int)
    return summary


def build_week_options(year: int, month: int) -> list[dict[str, object]]:
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    options = []
    cursor = first_day
    week_index = 1
    while cursor <= last_day:
        week_end = min(cursor + timedelta(days=6), last_day)
        options.append(
            {
                "index": week_index,
                "start": cursor,
                "end": week_end,
                "label": f"Week {week_index}: {cursor:%d/%m/%Y} - {week_end:%d/%m/%Y}",
            }
        )
        cursor = week_end + timedelta(days=1)
        week_index += 1
    return options


def month_options(df: pd.DataFrame) -> list[tuple[int, int, str]]:
    if df.empty:
        today = date.today()
        return [(today.year, today.month, f"{THAI_MONTH_BY_NUMBER[today.month]} {today.year}")]

    parsed = pd.to_datetime(df[DATE_COL], errors="coerce").dropna()
    periods = sorted({(item.year, item.month) for item in parsed}, reverse=True)
    return [
        (year, month, f"{THAI_MONTH_BY_NUMBER.get(month, month)} {year}")
        for year, month in periods
    ]


def vehicle_options(df: pd.DataFrame, query: str, limit: int = 50) -> list[str]:
    if df.empty or not query.strip():
        return []
    normalized_query = query.strip().upper().replace(" ", "")
    candidates = df[[PLATE_COL, NORMALIZED_PLATE_COL]].drop_duplicates()
    mask = (
        candidates[PLATE_COL].astype(str).str.contains(query.strip(), case=False, na=False)
        | candidates[NORMALIZED_PLATE_COL].astype(str).str.contains(normalized_query, case=False, na=False)
    )
    return candidates.loc[mask, PLATE_COL].head(limit).tolist()


def vehicle_profile(df: pd.DataFrame, plate: str) -> tuple[dict[str, object], pd.DataFrame]:
    if df.empty or not plate:
        return {}, pd.DataFrame()

    selected_norm = df.loc[df[PLATE_COL] == plate, NORMALIZED_PLATE_COL]
    if selected_norm.empty:
        return {}, pd.DataFrame()

    normalized_plate = selected_norm.iloc[0]
    history = (
        df[df[NORMALIZED_PLATE_COL] == normalized_plate]
        .sort_values(DATE_COL)
        .reset_index(drop=True)
    )
    if history.empty:
        return {}, history

    building_counts = history[BUILDING_COL].replace("", "ไม่ระบุอาคาร").value_counts()
    profile = {
        "plate": history[PLATE_COL].iloc[-1],
        "province": history[PROVINCE_COL].iloc[-1],
        "total_seen": int(len(history)),
        "top_building": building_counts.index[0] if not building_counts.empty else "-",
        "first_seen": history[DATE_COL].min(),
        "last_seen": history[DATE_COL].max(),
        "overnight_days": int(history[history[OVERNIGHT_COL] == True][DATE_COL].nunique()),
    }
    return profile, history

