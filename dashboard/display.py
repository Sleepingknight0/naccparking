from __future__ import annotations

import pandas as pd

from dashboard.data_service import (
    BUILDING_COL,
    DATE_COL,
    GAP_DAYS_COL,
    MONTH_COL,
    NEXT_SEEN_COL,
    NORMALIZED_PLATE_COL,
    OVERNIGHT_COL,
    OVERNIGHT_REASON_COL,
    PLATE_COL,
    PREV_SEEN_COL,
    PROVINCE_COL,
    RECORD_DATETIME_COL,
    REPEAT_COL,
    VEHICLE_KEY_COL,
    YEAR_COL,
    YEAR_MONTH_COL,
)


SYSTEM_COLUMN_LABELS = {
    "date_key": "วันที่ตรวจพบ",
    RECORD_DATETIME_COL: "วันที่/เวลาบันทึก",
    NORMALIZED_PLATE_COL: "ทะเบียนรถมาตรฐาน",
    VEHICLE_KEY_COL: "รหัสรถ",
    YEAR_COL: "ปี",
    MONTH_COL: "เดือน",
    YEAR_MONTH_COL: "ปี-เดือน",
    PREV_SEEN_COL: "วันที่พบก่อนหน้า",
    NEXT_SEEN_COL: "วันที่พบถัดไป",
    GAP_DAYS_COL: "ระยะห่างจากครั้งก่อนหน้า (วัน)",
    "next_gap_days": "ระยะห่างถึงครั้งถัดไป (วัน)",
    REPEAT_COL: "พบซ้ำ",
    OVERNIGHT_COL: "เข้าข่ายค้างคืน",
    OVERNIGHT_REASON_COL: "เหตุผลค้างคืนจากระบบ",
}

OPTIONAL_USER_COLUMNS = {
    "เวลา": "เวลา",
    "time": "เวลา",
    "ผู้บันทึก": "ผู้บันทึก",
    "officer": "ผู้บันทึก",
    "recorder": "ผู้บันทึก",
    "หมายเหตุ": "หมายเหตุ",
    "note": "หมายเหตุ",
}

SYSTEM_COLUMNS = set(SYSTEM_COLUMN_LABELS)
DEFAULT_OUTPUT_COLUMNS = [
    "วันที่",
    "เวลา",
    "ทะเบียนรถ",
    "จังหวัด",
    "อาคาร",
    "ผู้บันทึก",
    "หมายเหตุ",
    "สถานะค้างคืน",
    "เหตุผลค้างคืน",
]


def prepare_display_dataframe(
    df: pd.DataFrame,
    include_system_columns: bool = False,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=_empty_columns(include_system_columns))

    work = df.copy()
    display = pd.DataFrame(index=work.index)

    _assign_if_present(display, work, DATE_COL, "วันที่", formatter=_format_date)
    _assign_optional_columns(display, work)
    _assign_if_present(display, work, PLATE_COL, "ทะเบียนรถ")
    _assign_if_present(display, work, PROVINCE_COL, "จังหวัด")
    _assign_if_present(display, work, BUILDING_COL, "อาคาร")

    if OVERNIGHT_COL in work.columns:
        display["สถานะค้างคืน"] = work[OVERNIGHT_COL].map(_format_overnight_status)
    else:
        display["สถานะค้างคืน"] = "ไม่ระบุ"

    if OVERNIGHT_REASON_COL in work.columns:
        display["เหตุผลค้างคืน"] = work[OVERNIGHT_REASON_COL].fillna("-").replace("", "-")
    else:
        display["เหตุผลค้างคืน"] = "-"

    display = display[[column for column in DEFAULT_OUTPUT_COLUMNS if column in display.columns]]

    if include_system_columns:
        display = pd.concat([display, _system_display_columns(work)], axis=1)

    display = display.reset_index(drop=True)
    display.columns = make_unique_columns(display.columns)
    assert display.columns.is_unique
    return display


def make_unique_columns(columns) -> list[str]:
    seen: dict[str, int] = {}
    unique: list[str] = []
    for column in columns:
        base = str(column)
        count = seen.get(base, 0)
        seen[base] = count + 1
        if count == 0:
            unique.append(base)
        else:
            unique.append(f"{base} ({count + 1})")
    return unique


def _assign_optional_columns(display: pd.DataFrame, work: pd.DataFrame) -> None:
    used_labels = set(display.columns)
    for source, label in OPTIONAL_USER_COLUMNS.items():
        if source in work.columns and label not in used_labels:
            display[label] = work[source].fillna("").astype(str)
            used_labels.add(label)


def _assign_if_present(
    display: pd.DataFrame,
    work: pd.DataFrame,
    source: str,
    label: str,
    formatter=None,
) -> None:
    if source not in work.columns:
        return
    values = work[source]
    display[label] = values.map(formatter) if formatter else values


def _system_display_columns(work: pd.DataFrame) -> pd.DataFrame:
    system = pd.DataFrame(index=work.index)
    for source, label in SYSTEM_COLUMN_LABELS.items():
        if source not in work.columns:
            continue
        if label in system.columns:
            continue
        system[label] = work[source].map(_format_system_value)
    return system


def _empty_columns(include_system_columns: bool) -> list[str]:
    columns = [column for column in DEFAULT_OUTPUT_COLUMNS if column not in {"เวลา", "ผู้บันทึก", "หมายเหตุ"}]
    if include_system_columns:
        columns.extend(SYSTEM_COLUMN_LABELS.values())
    return make_unique_columns(columns)


def _format_date(value: object) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    return "" if pd.isna(value) else str(value)


def _format_system_value(value: object) -> object:
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y %H:%M:%S") if hasattr(value, "hour") else value.strftime("%d/%m/%Y")
    if isinstance(value, bool):
        return "ใช่" if value else "ไม่ใช่"
    return "" if pd.isna(value) else value


def _format_overnight_status(value: object) -> str:
    return "เข้าข่ายค้างคืน" if bool(value) else "ไม่เข้าข่าย"
