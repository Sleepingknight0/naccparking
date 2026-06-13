import calendar
import datetime as dt
import io
from pathlib import Path

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


def to_summary_pdf_bytes(df, report_label):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    font_name = _register_pdf_font()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ThaiTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=18,
        leading=24,
        spaceAfter=8,
    )
    normal_style = ParagraphStyle(
        "ThaiNormal",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=14,
    )

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    story = [
        Paragraph("รายงานรถค้างอาคาร", title_style),
        Paragraph(report_label, normal_style),
        Spacer(1, 0.35 * cm),
    ]

    summary_rows = [
        ["รายการ", "จำนวน"],
        ["จำนวนรถในรายงาน", str(len(df))],
        ["รถใหม่ในช่วงนี้", str(_count_status(df, "ใหม่ในช่วงนี้"))],
        ["รถที่เคยพบมาก่อน", str(_count_status(df, "เคยพบมาก่อน"))],
        ["รถสถานะเฝ้าดู", str(_count_status(df, "เฝ้าดู"))],
        ["รถเกิน 7 วัน", str(_count_status(df, "เกิน 7 วัน"))],
    ]
    story.append(_build_pdf_table(summary_rows, font_name, [10 * cm, 4 * cm]))
    story.append(Spacer(1, 0.45 * cm))

    top_rows = [["ลำดับ", "ทะเบียน", "จังหวัด", "อาคารล่าสุด", "วันในช่วง", "สถานะ"]]
    for _, row in df.head(20).iterrows():
        top_rows.append(
            [
                str(row.get("ลำดับ", "")),
                str(row.get("ทะเบียนรถ", "")),
                str(row.get("จังหวัด", "")),
                str(row.get("อาคารล่าสุด", "")),
                str(row.get("จำนวนวันที่พบในช่วง", "")),
                str(row.get("สถานะ", "")),
            ]
        )
    story.append(Paragraph("รายการรถ", normal_style))
    story.append(Spacer(1, 0.2 * cm))
    story.append(
        _build_pdf_table(top_rows, font_name, [1.4 * cm, 2.8 * cm, 3 * cm, 3.2 * cm, 1.9 * cm, 3 * cm])
    )

    doc.build(story)
    return buffer.getvalue()


def to_summary_jpg_bytes(df, report_label):
    from PIL import Image, ImageDraw, ImageFont

    width = 1400
    row_height = 48
    table_rows = min(len(df), 18)
    height = 430 + (table_rows + 1) * row_height
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = _load_image_font(34)
    heading_font = _load_image_font(24)
    body_font = _load_image_font(20)
    small_font = _load_image_font(18)

    x = 60
    y = 50
    draw.text((x, y), "รายงานรถค้างอาคาร", fill="#17324d", font=title_font)
    y += 50
    draw.text((x, y), report_label, fill="#334155", font=body_font)
    y += 55

    summary = [
        ("จำนวนรถในรายงาน", len(df)),
        ("รถใหม่ในช่วงนี้", _count_status(df, "ใหม่ในช่วงนี้")),
        ("รถที่เคยพบมาก่อน", _count_status(df, "เคยพบมาก่อน")),
        ("รถสถานะเฝ้าดู", _count_status(df, "เฝ้าดู")),
        ("รถเกิน 7 วัน", _count_status(df, "เกิน 7 วัน")),
    ]
    card_width = 245
    card_height = 92
    for index, (label, value) in enumerate(summary):
        card_x = x + index * (card_width + 15)
        draw.rounded_rectangle(
            (card_x, y, card_x + card_width, y + card_height),
            radius=12,
            fill="#f1f5f9",
            outline="#cbd5e1",
        )
        draw.text((card_x + 18, y + 16), label, fill="#475569", font=small_font)
        draw.text((card_x + 18, y + 48), str(value), fill="#0f172a", font=heading_font)
    y += 130

    draw.text((x, y), "รายการรถ", fill="#17324d", font=heading_font)
    y += 42
    columns = [
        ("ลำดับ", 80),
        ("ทะเบียน", 180),
        ("จังหวัด", 230),
        ("อาคารล่าสุด", 240),
        ("วันในช่วง", 120),
        ("สถานะ", 220),
    ]
    table_x = x
    draw.rectangle((table_x, y, width - x, y + row_height), fill="#e8eef5", outline="#b9c4cf")
    current_x = table_x
    for label, col_width in columns:
        draw.text((current_x + 12, y + 12), label, fill="#17324d", font=small_font)
        current_x += col_width
    y += row_height

    for row_index, (_, row) in enumerate(df.head(table_rows).iterrows()):
        fill = "#ffffff" if row_index % 2 == 0 else "#f8fafc"
        draw.rectangle((table_x, y, width - x, y + row_height), fill=fill, outline="#d8e0e8")
        values = [
            row.get("ลำดับ", ""),
            row.get("ทะเบียนรถ", ""),
            row.get("จังหวัด", ""),
            row.get("อาคารล่าสุด", ""),
            row.get("จำนวนวันที่พบในช่วง", ""),
            row.get("สถานะ", ""),
        ]
        current_x = table_x
        for value, (_, col_width) in zip(values, columns):
            draw.text((current_x + 12, y + 12), str(value), fill="#0f172a", font=small_font)
            current_x += col_width
        y += row_height

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


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


def _count_status(df, status):
    if "สถานะ" not in df.columns:
        return 0
    return int((df["สถานะ"] == status).sum())


def _build_pdf_table(rows, font_name, column_widths):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    table = Table(rows, colWidths=column_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17324d")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b9c4cf")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _register_pdf_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        Path("assets/fonts/NotoSansThai-Regular.ttf"),
        Path("C:/Windows/Fonts/tahoma.ttf"),
        Path("C:/Windows/Fonts/THSarabunNew.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"),
        Path("/usr/share/fonts/truetype/thai/Garuda.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for font_path in candidates:
        if font_path.exists():
            pdfmetrics.registerFont(TTFont("ReportThai", str(font_path)))
            return "ReportThai"
    return "Helvetica"


def _load_image_font(size):
    from PIL import ImageFont

    candidates = [
        Path("assets/fonts/NotoSansThai-Regular.ttf"),
        Path("C:/Windows/Fonts/tahoma.ttf"),
        Path("C:/Windows/Fonts/THSarabunNew.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"),
        Path("/usr/share/fonts/truetype/thai/Garuda.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for font_path in candidates:
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default()
