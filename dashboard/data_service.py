from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from services.google_sheets_service import read_parking_values


DATE_COL = "วันที่ตรวจพบ"
BUILDING_COL = "อาคาร"
PLATE_COL = "ทะเบียนรถ"
PROVINCE_COL = "จังหวัด"

NORMALIZED_PLATE_COL = "normalized_plate"
VEHICLE_KEY_COL = "vehicle_key"
PREV_SEEN_COL = "prev_seen_date"
NEXT_SEEN_COL = "next_seen_date"
GAP_DAYS_COL = "gap_days"
REPEAT_COL = "is_repeat_vehicle"
OVERNIGHT_COL = "is_overnight_candidate"
OVERNIGHT_REASON_COL = "overnight_reason"
RECORD_DATETIME_COL = "record_datetime"
YEAR_COL = "year"
MONTH_COL = "month"
YEAR_MONTH_COL = "year_month"

CANONICAL_COLUMNS = [DATE_COL, BUILDING_COL, PLATE_COL, PROVINCE_COL]
DERIVED_COLUMNS = [
    NORMALIZED_PLATE_COL,
    VEHICLE_KEY_COL,
    PREV_SEEN_COL,
    NEXT_SEEN_COL,
    GAP_DAYS_COL,
    REPEAT_COL,
    OVERNIGHT_COL,
    OVERNIGHT_REASON_COL,
    RECORD_DATETIME_COL,
    YEAR_COL,
    MONTH_COL,
    YEAR_MONTH_COL,
]

COLUMN_ALIASES = {
    DATE_COL: [
        DATE_COL,
        "วันที่บันทึก",
        "วันที่พบ",
        "Timestamp",
        "Date",
        "created_at",
        "found_date",
        "date_key",
    ],
    BUILDING_COL: [BUILDING_COL, "building", "อาคารที่พบ", "location"],
    PLATE_COL: [PLATE_COL, "ทะเบียนรถยนต์", "plate", "license_plate", "ทะเบียน"],
    PROVINCE_COL: [PROVINCE_COL, "province", "จังหวัดรถ", "plate_province"],
}

STATUS_ALIASES = ["สถานะ", "status", "overnight_status", "ค้างคืน", "หมายเหตุ", "note"]
OVERNIGHT_STATUS_KEYWORDS = ["ค้าง", "overnight", "ต่อเนื่อง", "ข้ามคืน"]


@dataclass(frozen=True)
class DashboardDataResult:
    raw: pd.DataFrame
    prepared: pd.DataFrame
    loaded_at: datetime | None
    error: str | None = None


def normalize_plate(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip().upper()
    text = re.sub(r"[\s\-.‐‑‒–—]+", "", text)
    return text


def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    canonical = df.copy()
    canonical.columns = _unique_headers(canonical.columns)
    normalized_lookup = {_normalize_header(column): column for column in canonical.columns}

    for target, aliases in COLUMN_ALIASES.items():
        if target in canonical.columns:
            continue
        source = next(
            (
                normalized_lookup[_normalize_header(alias)]
                for alias in aliases
                if _normalize_header(alias) in normalized_lookup
            ),
            None,
        )
        if source is not None:
            canonical = canonical.rename(columns={source: target})

    for column in CANONICAL_COLUMNS:
        if column not in canonical.columns:
            canonical[column] = pd.NA

    return canonical


def prepare_dashboard_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    prepared = canonicalize_columns(df)
    if prepared.empty:
        return _empty_prepared_dataframe(prepared)

    prepared = prepared.drop_duplicates().copy()
    parsed_dates = _parse_date_series(prepared[DATE_COL])
    prepared[RECORD_DATETIME_COL] = parsed_dates
    prepared[DATE_COL] = parsed_dates.dt.date

    for column in [BUILDING_COL, PLATE_COL, PROVINCE_COL]:
        prepared[column] = _clean_text_series(prepared[column])

    if "ทะเบียน_clean" in prepared.columns:
        clean_source = prepared["ทะเบียน_clean"].where(
            prepared["ทะเบียน_clean"].astype(str).str.strip() != "",
            prepared[PLATE_COL],
        )
    else:
        clean_source = prepared[PLATE_COL]
    prepared[NORMALIZED_PLATE_COL] = clean_source.map(normalize_plate)
    prepared[VEHICLE_KEY_COL] = prepared[NORMALIZED_PLATE_COL]
    prepared[YEAR_COL] = parsed_dates.dt.year
    prepared[MONTH_COL] = parsed_dates.dt.month
    prepared[YEAR_MONTH_COL] = parsed_dates.dt.strftime("%Y-%m")

    prepared = prepared.dropna(subset=[DATE_COL])
    prepared = prepared[prepared[NORMALIZED_PLATE_COL] != ""]
    if prepared.empty:
        return _empty_prepared_dataframe(prepared)

    prepared = prepared.sort_values(
        by=[NORMALIZED_PLATE_COL, DATE_COL, BUILDING_COL, PROVINCE_COL],
        kind="stable",
    ).reset_index(drop=True)
    prepared[PREV_SEEN_COL] = prepared.groupby(NORMALIZED_PLATE_COL)[DATE_COL].shift(1)
    prepared[NEXT_SEEN_COL] = prepared.groupby(NORMALIZED_PLATE_COL)[DATE_COL].shift(-1)
    prepared[GAP_DAYS_COL] = _date_gap(prepared[PREV_SEEN_COL], prepared[DATE_COL])
    prepared["next_gap_days"] = _date_gap(prepared[DATE_COL], prepared[NEXT_SEEN_COL])

    date_counts = prepared.groupby(NORMALIZED_PLATE_COL)[DATE_COL].transform("nunique")
    prepared[REPEAT_COL] = date_counts > 1

    status_match = _status_indicates_overnight(prepared)
    consecutive_match = (prepared[GAP_DAYS_COL] == 1) | (prepared["next_gap_days"] == 1)
    prepared[OVERNIGHT_COL] = status_match | consecutive_match
    prepared[OVERNIGHT_REASON_COL] = [
        _overnight_reason(status, prev_gap, next_gap)
        for status, prev_gap, next_gap in zip(
            status_match,
            prepared[GAP_DAYS_COL],
            prepared["next_gap_days"],
        )
    ]

    return prepared.reset_index(drop=True)


@st.cache_resource(show_spinner=False)
def init_dashboard_spreadsheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError("ไม่พบข้อมูล gcp_service_account ใน st.secrets")
    if "spreadsheet_url" not in st.secrets:
        raise RuntimeError("ไม่พบข้อมูล spreadsheet_url ใน st.secrets")

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes,
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_url(st.secrets["spreadsheet_url"])
    return spreadsheet


@st.cache_resource(show_spinner=False)
def init_dashboard_connection():
    return init_dashboard_spreadsheet().worksheet("RawData")


@st.cache_data(ttl=300, show_spinner=False)
def load_raw_dashboard_data() -> pd.DataFrame:
    sheet = init_dashboard_connection()
    values = read_parking_values(sheet)
    return dataframe_from_sheet_values(values)


@st.cache_data(ttl=300, show_spinner=False)
def load_archive_month(year: int, month: int) -> pd.DataFrame:
    """Load exactly one archive sheet; normal dashboard loading never calls this."""
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")
    sheet_name = f"Archive_{year:04d}_{month:02d}"
    try:
        sheet = init_dashboard_spreadsheet().worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)
    return dataframe_from_sheet_values(sheet.get("A1:Z"))


def load_archive_months(months: Iterable[tuple[int, int]]) -> pd.DataFrame:
    """Load only explicitly selected months and combine their rows."""
    frames = [load_archive_month(year, month) for year, month in months]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=CANONICAL_COLUMNS)


@st.cache_data(ttl=300, show_spinner=False)
def load_prepared_dashboard_data() -> tuple[pd.DataFrame, pd.DataFrame, datetime]:
    raw = load_raw_dashboard_data()
    prepared = prepare_dashboard_dataframe(raw)
    return raw, prepared, datetime.now().astimezone()


def get_dashboard_data() -> DashboardDataResult:
    try:
        raw, prepared, loaded_at = load_prepared_dashboard_data()
        return DashboardDataResult(raw=raw, prepared=prepared, loaded_at=loaded_at)
    except Exception as exc:
        empty_raw = pd.DataFrame(columns=CANONICAL_COLUMNS)
        empty_prepared = prepare_dashboard_dataframe(empty_raw)
        return DashboardDataResult(
            raw=empty_raw,
            prepared=empty_prepared,
            loaded_at=None,
            error=str(exc),
        )


def clear_dashboard_cache() -> None:
    load_raw_dashboard_data.clear()
    load_prepared_dashboard_data.clear()


def dataframe_from_sheet_values(values: list[list[object]]) -> pd.DataFrame:
    if not values:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    width = max(len(row) for row in values)
    raw_headers = _padded_row(values[0], width)
    # RawData's verified live schema has blank C/D headers while the app writes
    # plate and province there. Name only those known positions before uniquifying.
    for index, canonical_name in enumerate(CANONICAL_COLUMNS):
        if index < len(raw_headers) and not str(raw_headers[index] or "").strip():
            raw_headers[index] = canonical_name
    headers = _unique_headers(raw_headers)
    rows = [_padded_row(row, width) for row in values[1:]]
    return pd.DataFrame(rows, columns=headers)


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="RawData")
    return output.getvalue()


def _empty_prepared_dataframe(base: pd.DataFrame | None = None) -> pd.DataFrame:
    columns = list(base.columns) if base is not None else CANONICAL_COLUMNS
    for column in CANONICAL_COLUMNS + DERIVED_COLUMNS + ["next_gap_days"]:
        if column not in columns:
            columns.append(column)
    return pd.DataFrame(columns=columns)


def _clean_text_series(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def _parse_date_series(series: pd.Series) -> pd.Series:
    as_text = series.astype(str).str.strip()
    parsed = pd.to_datetime(series, errors="coerce")
    slash_mask = as_text.str.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", na=False)
    if slash_mask.any():
        parsed.loc[slash_mask] = pd.to_datetime(
            as_text.loc[slash_mask],
            dayfirst=True,
            errors="coerce",
        )
    return pd.Series(parsed, index=series.index)


def _date_gap(start_series: pd.Series, end_series: pd.Series) -> pd.Series:
    start = pd.to_datetime(start_series, errors="coerce")
    end = pd.to_datetime(end_series, errors="coerce")
    return (end - start).dt.days


def _status_indicates_overnight(df: pd.DataFrame) -> pd.Series:
    status_columns = [
        column
        for column in df.columns
        if _normalize_header(column) in {_normalize_header(alias) for alias in STATUS_ALIASES}
    ]
    if not status_columns:
        return pd.Series(False, index=df.index)

    combined = (
        df[status_columns]
        .fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
        .str.lower()
    )
    return combined.apply(
        lambda text: any(keyword.lower() in text for keyword in OVERNIGHT_STATUS_KEYWORDS)
    )


def _overnight_reason(status_match: bool, prev_gap: object, next_gap: object) -> str:
    if status_match:
        return "สถานะใน Sheet ระบุว่าค้างคืน"
    if prev_gap == 1 and next_gap == 1:
        return "พบต่อเนื่องกับวันก่อนและวันถัดไป"
    if prev_gap == 1:
        return "พบต่อเนื่องจากวันก่อนหน้า"
    if next_gap == 1:
        return "พบต่อเนื่องกับวันถัดไป"
    return "-"


def _unique_headers(headers: Iterable[object]) -> list[str]:
    unique = []
    seen: dict[str, int] = {}
    for index, raw_header in enumerate(headers):
        header = str(raw_header).strip() if raw_header is not None else ""
        if not header:
            header = f"คอลัมน์ว่าง {index + 1}"
        count = seen.get(header, 0)
        seen[header] = count + 1
        unique.append(header if count == 0 else f"{header}_{count + 1}")
    return unique


def _normalize_header(value: object) -> str:
    return re.sub(r"[\s_\-]+", "", str(value).strip().lower())


def _padded_row(row: list[object], width: int) -> list[object]:
    return list(row) + [""] * (width - len(row))

