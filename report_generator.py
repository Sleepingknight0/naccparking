import calendar
import datetime as dt

import pandas as pd


REPORT_COLUMNS = [
    "ลำดับ",
    "ช่วงรายงาน",
    "วันที่เริ่มพบในช่วง",
    "วันที่พบล่าสุดในช่วง",
    "อาคารล่าสุด",
    "ทะเบียนรถ",
    "จังหวัด",
    "ทะเบียน_clean",
    "จำนวนวันที่พบในช่วง",
    "จำนวนวันที่พบทั้งหมด",
    "สถานะ",
]


def get_report_period(report_type, selected_date):
    selected_date = _as_date(selected_date)

    if report_type == "รายวัน":
        return selected_date, selected_date, f"ประจำวันที่ {selected_date:%d/%m/%Y}"

    if report_type == "รายสัปดาห์":
        start = selected_date - dt.timedelta(days=selected_date.weekday())
        end = start + dt.timedelta(days=6)
        return start, end, f"ประจำสัปดาห์ {start:%d/%m/%Y} - {end:%d/%m/%Y}"

    if report_type == "รายเดือน":
        start = selected_date.replace(day=1)
        end = selected_date.replace(
            day=calendar.monthrange(selected_date.year, selected_date.month)[1]
        )
        return start, end, f"ประจำเดือน {selected_date:%m/%Y}"

    raise ValueError(f"ไม่รู้จักประเภทรายงาน: {report_type}")


def build_detailed_report(df, report_type, selected_date):
    start, end, label = get_report_period(report_type, selected_date)
    prepared = _prepare_data(df)
    if prepared.empty:
        return pd.DataFrame(columns=REPORT_COLUMNS)

    in_period = prepared[
        (prepared["วันที่ตรวจพบ"] >= start) & (prepared["วันที่ตรวจพบ"] <= end)
    ].drop_duplicates(subset=["วันที่ตรวจพบ", "ทะเบียน_clean", "จังหวัด"])
    if in_period.empty:
        return pd.DataFrame(columns=REPORT_COLUMNS)

    days_in_period = (
        in_period.groupby(["ทะเบียน_clean", "จังหวัด"])["วันที่ตรวจพบ"]
        .nunique()
        .reset_index(name="จำนวนวันที่พบในช่วง")
    )
    total_days = (
        prepared.drop_duplicates(subset=["วันที่ตรวจพบ", "ทะเบียน_clean", "จังหวัด"])
        .groupby(["ทะเบียน_clean", "จังหวัด"])["วันที่ตรวจพบ"]
        .nunique()
        .reset_index(name="จำนวนวันที่พบทั้งหมด")
    )
    first_seen = (
        prepared.groupby(["ทะเบียน_clean", "จังหวัด"])["วันที่ตรวจพบ"]
        .min()
        .reset_index(name="พบครั้งแรกทั้งหมด")
    )
    latest_rows = (
        in_period.sort_values("วันที่ตรวจพบ")
        .drop_duplicates(subset=["ทะเบียน_clean", "จังหวัด"], keep="last")
        [["ทะเบียน_clean", "จังหวัด", "วันที่ตรวจพบ", "อาคาร", "ทะเบียนรถ"]]
        .rename(columns={"วันที่ตรวจพบ": "วันที่พบล่าสุดในช่วง", "อาคาร": "อาคารล่าสุด"})
    )
    first_in_period = (
        in_period.groupby(["ทะเบียน_clean", "จังหวัด"])["วันที่ตรวจพบ"]
        .min()
        .reset_index(name="วันที่เริ่มพบในช่วง")
    )

    report = (
        days_in_period.merge(total_days, on=["ทะเบียน_clean", "จังหวัด"], how="left")
        .merge(first_seen, on=["ทะเบียน_clean", "จังหวัด"], how="left")
        .merge(latest_rows, on=["ทะเบียน_clean", "จังหวัด"], how="left")
        .merge(first_in_period, on=["ทะเบียน_clean", "จังหวัด"], how="left")
    )
    report["ช่วงรายงาน"] = label
    report["สถานะ"] = report.apply(
        lambda row: _status_for_row(row, start),
        axis=1,
    )
    report = report.sort_values(
        by=["จำนวนวันที่พบในช่วง", "วันที่พบล่าสุดในช่วง", "ทะเบียน_clean"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    report.insert(0, "ลำดับ", range(1, len(report) + 1))

    return report[REPORT_COLUMNS]


def to_csv_bytes(df):
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def make_report_filename(report_type, selected_date, extension):
    start, end, _ = get_report_period(report_type, selected_date)
    if start == end:
        date_part = start.strftime("%Y%m%d")
    else:
        date_part = f"{start:%Y%m%d}-{end:%Y%m%d}"
    return f"naccparking-{report_type}-{date_part}.{extension}"


def _prepare_data(df):
    required_columns = ["วันที่ตรวจพบ", "อาคาร", "ทะเบียนรถ", "จังหวัด"]
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"ข้อมูลขาดคอลัมน์: {', '.join(missing_columns)}")

    prepared = df[required_columns].copy()
    prepared["วันที่ตรวจพบ"] = pd.to_datetime(
        prepared["วันที่ตรวจพบ"], errors="coerce"
    ).dt.date
    prepared["ทะเบียนรถ"] = prepared["ทะเบียนรถ"].astype(str).str.strip()
    prepared["จังหวัด"] = prepared["จังหวัด"].astype(str).str.strip()
    prepared["อาคาร"] = prepared["อาคาร"].astype(str).str.strip()
    prepared["ทะเบียน_clean"] = (
        prepared["ทะเบียนรถ"].str.upper().str.replace(r"[\s\-.]", "", regex=True)
    )
    return prepared.dropna(subset=["วันที่ตรวจพบ"])


def _as_date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return pd.to_datetime(value).date()


def _status_for_row(row, period_start):
    if row["พบครั้งแรกทั้งหมด"] >= period_start:
        return "ใหม่ในช่วงนี้"
    if row["จำนวนวันที่พบในช่วง"] >= 7:
        return "เกิน 7 วัน"
    if row["จำนวนวันที่พบในช่วง"] >= 3:
        return "เฝ้าดู"
    return "เคยพบมาก่อน"
