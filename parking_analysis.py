import pandas as pd


LONG_PARKING_DAYS_COLUMN = "จำนวนวันที่จอดสะสม (วัน)"
OUTPUT_COLUMNS = ["ทะเบียนรถ", "จังหวัด", "อาคาร", LONG_PARKING_DAYS_COLUMN]
PARKING_KEY_COLUMNS = ["ทะเบียน_clean", "จังหวัด"]


def summarize_long_parkers(df, days_threshold):
    if df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    parking_days = df.copy()
    parking_days["วันที่ตรวจพบ"] = pd.to_datetime(
        parking_days["วันที่ตรวจพบ"], errors="coerce"
    ).dt.date
    parking_days["ทะเบียน_clean"] = (
        parking_days["ทะเบียนรถ"].astype(str).str.upper().str.strip()
        .str.replace(r"[\s\-.]", "", regex=True)
    )
    parking_days["จังหวัด"] = parking_days["จังหวัด"].astype(str).str.strip()
    parking_days = parking_days.dropna(subset=["วันที่ตรวจพบ"])
    parking_days = parking_days.drop_duplicates(
        subset=["วันที่ตรวจพบ", *PARKING_KEY_COLUMNS]
    )

    summary = (
        parking_days.groupby(PARKING_KEY_COLUMNS)["วันที่ตรวจพบ"]
        .nunique()
        .reset_index(name=LONG_PARKING_DAYS_COLUMN)
    )
    latest_rows = (
        parking_days.sort_values("วันที่ตรวจพบ")
        .drop_duplicates(subset=PARKING_KEY_COLUMNS, keep="last")
        [PARKING_KEY_COLUMNS + ["ทะเบียนรถ", "อาคาร"]]
    )
    summary = summary.merge(latest_rows, on=PARKING_KEY_COLUMNS, how="left")
    long_parkers = summary[summary[LONG_PARKING_DAYS_COLUMN] >= days_threshold]

    return long_parkers.sort_values(
        by=LONG_PARKING_DAYS_COLUMN, ascending=False
    ).reset_index(drop=True)[OUTPUT_COLUMNS]
