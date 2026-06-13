import calendar
import datetime as dt
import html
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

FONT_DIRECTORIES = [
    Path("font"),
    Path("assets/fonts"),
]

FONT_CANDIDATES = [
    Path("font/THSarabunIT๙.ttf"),
    Path("font/TH NiramitIT๙.ttf"),
    Path("font/Sarabun-Regular.ttf"),
    Path("font/NotoSansThai-Regular.ttf"),
    Path("font/Kanit-Regular.ttf"),
    Path("font/Prompt-Regular.ttf"),
    Path("assets/fonts/THSarabunNew.ttf"),
    Path("assets/fonts/THSarabun.ttf"),
    Path("assets/fonts/THSarabunNew/THSarabunNew.ttf"),
    Path("assets/fonts/NotoSansThai-Regular.ttf"),
    Path("C:/Windows/Fonts/THSarabunNew.ttf"),
    Path("C:/Windows/Fonts/tahoma.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"),
    Path("/usr/share/fonts/truetype/thai/Garuda.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]

REPORT_FONT_CHOICES = {
    "TH Sarabun IT๙": Path("font/THSarabunIT๙.ttf"),
    "TH Niramit IT๙": Path("font/TH NiramitIT๙.ttf"),
    "Sarabun": Path("font/Sarabun-Regular.ttf"),
    "Noto Sans Thai": Path("font/NotoSansThai-Regular.ttf"),
    "Kanit": Path("font/Kanit-Regular.ttf"),
    "Prompt": Path("font/Prompt-Regular.ttf"),
}

PDF_FONT_SIZES = {
    "title": 24,
    "heading": 20,
    "body": 16,
    "table": 14,
}

IMAGE_FONT_SIZES = {
    "title": 24,
    "heading": 20,
    "body": 16,
    "small": 14,
}


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


def to_summary_pdf_bytes(df, report_label, font_path=None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    font_name = _register_pdf_font(font_path)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ThaiTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=PDF_FONT_SIZES["title"],
        leading=28,
        spaceAfter=5,
    )
    heading_style = ParagraphStyle(
        "ThaiHeading",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=PDF_FONT_SIZES["heading"],
        leading=24,
        spaceBefore=4,
        spaceAfter=5,
    )
    normal_style = ParagraphStyle(
        "ThaiNormal",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=PDF_FONT_SIZES["body"],
        leading=19,
    )
    detail_style = ParagraphStyle(
        "ThaiDetail",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=PDF_FONT_SIZES["table"],
        leading=17,
    )

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    story = [
        Paragraph("รายงานรถค้างอาคาร", title_style),
        Paragraph(report_label, normal_style),
        Spacer(1, 0.2 * cm),
    ]

    summary_rows = [
        ["รายการ", "จำนวน"],
        ["จำนวนรถในรายงาน", str(len(df))],
        ["รถใหม่ในช่วงนี้", str(_count_status(df, "ใหม่ในช่วงนี้"))],
        ["รถที่เคยพบมาก่อน", str(_count_status(df, "เคยพบมาก่อน"))],
        ["รถสถานะเฝ้าดู", str(_count_status(df, "เฝ้าดู"))],
        ["รถเกิน 7 วัน", str(_count_status(df, "เกิน 7 วัน"))],
    ]
    story.append(_build_pdf_table(summary_rows, font_name, [12 * cm, 4 * cm]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("รายการรถ", heading_style))
    story.append(Spacer(1, 0.1 * cm))
    for _, row in df.iterrows():
        story.append(_build_pdf_vehicle_card(row, normal_style, detail_style))
        story.append(Spacer(1, 0.08 * cm))

    doc.build(story)
    return buffer.getvalue()


def to_summary_jpg_bytes(df, report_label, font_path=None):
    from PIL import Image, ImageDraw

    width = 1080
    item_height = 82
    item_count = len(df)
    height = 430 + (item_count * item_height)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = _load_image_font(IMAGE_FONT_SIZES["title"], font_path)
    heading_font = _load_image_font(IMAGE_FONT_SIZES["heading"], font_path)
    body_font = _load_image_font(IMAGE_FONT_SIZES["body"], font_path)
    small_font = _load_image_font(IMAGE_FONT_SIZES["small"], font_path)

    x = 56
    y = 38
    draw.text((x, y), "รายงานรถค้างอาคาร", fill="#17324d", font=title_font)
    y += 36
    draw.text((x, y), report_label, fill="#334155", font=body_font)
    y += 42

    summary = [
        ("จำนวนรถในรายงาน", len(df)),
        ("รถใหม่ในช่วงนี้", _count_status(df, "ใหม่ในช่วงนี้")),
        ("รถที่เคยพบมาก่อน", _count_status(df, "เคยพบมาก่อน")),
        ("รถสถานะเฝ้าดู", _count_status(df, "เฝ้าดู")),
        ("รถเกิน 7 วัน", _count_status(df, "เกิน 7 วัน")),
    ]
    card_width = 462
    card_height = 62
    for index, (label, value) in enumerate(summary):
        card_x = x + (index % 2) * (card_width + 44)
        card_y = y + (index // 2) * (card_height + 16)
        draw.rounded_rectangle(
            (card_x, card_y, card_x + card_width, card_y + card_height),
            radius=12,
            fill="#f1f5f9",
            outline="#cbd5e1",
        )
        draw.text((card_x + 16, card_y + 9), label, fill="#475569", font=small_font)
        draw.text((card_x + 16, card_y + 32), str(value), fill="#0f172a", font=heading_font)
    y += 220

    draw.text((x, y), "รายการรถ", fill="#17324d", font=heading_font)
    y += 32

    card_width = width - (x * 2)
    for row_index, (_, row) in enumerate(df.iterrows()):
        fill = "#ffffff" if row_index % 2 == 0 else "#f8fafc"
        draw.rounded_rectangle(
            (x, y, x + card_width, y + item_height - 8),
            radius=10,
            fill=fill,
            outline="#d8e0e8",
        )
        first_line, second_line, third_line = _format_report_row_lines(row)
        draw.text((x + 16, y + 9), _fit_text(draw, first_line, body_font, card_width - 32), fill="#0f172a", font=body_font)
        draw.text((x + 16, y + 34), _fit_text(draw, second_line, small_font, card_width - 32), fill="#334155", font=small_font)
        draw.text((x + 16, y + 56), _fit_text(draw, third_line, small_font, card_width - 32), fill="#475569", font=small_font)
        y += item_height

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


def get_report_font_options():
    options = {"อัตโนมัติ (ค่าแนะนำ)": None}

    for fonts_dir in FONT_DIRECTORIES:
        if fonts_dir.exists():
            font_files = sorted(list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf")))
            for font_path in font_files:
                options.setdefault(_font_label(font_path), str(font_path))

    for label, font_path in REPORT_FONT_CHOICES.items():
        options.setdefault(label, str(font_path))

    for font_path in FONT_CANDIDATES:
        if font_path.exists():
            options.setdefault(_font_label(font_path), str(font_path))

    return options


def resolve_font_candidates(font_path=None):
    candidates = []
    if font_path:
        candidates.append(Path(font_path))
    candidates.extend(FONT_CANDIDATES)

    unique_candidates = []
    seen = set()
    for candidate in candidates:
        candidate_key = str(candidate)
        if candidate_key not in seen:
            unique_candidates.append(candidate)
            seen.add(candidate_key)
    return unique_candidates


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


def _build_pdf_vehicle_card(row, normal_style, detail_style):
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Table, TableStyle

    first_line, second_line, third_line = _format_report_row_lines(row)
    table = Table(
        [
            [Paragraph(_escape_pdf_text(first_line), normal_style)],
            [Paragraph(_escape_pdf_text(second_line), detail_style)],
            [Paragraph(_escape_pdf_text(third_line), detail_style)],
        ],
        colWidths=[16.8 * cm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8e0e8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _format_report_row_lines(row):
    first_line = (
        f"{row.get('ลำดับ', '')}. ทะเบียน {row.get('ทะเบียนรถ', '')} "
        f"จังหวัด {row.get('จังหวัด', '')}"
    )
    second_line = (
        f"อาคารล่าสุด: {row.get('อาคารล่าสุด', '')} | "
        f"พบล่าสุด: {_format_date_value(row.get('วันที่พบล่าสุดในช่วง', ''))}"
    )
    third_line = (
        f"วันในช่วง: {row.get('จำนวนวันที่พบในช่วง', '')} | "
        f"รวมทั้งหมด: {row.get('จำนวนวันที่พบทั้งหมด', '')} | "
        f"สถานะ: {row.get('สถานะ', '')}"
    )
    return first_line, second_line, third_line


def _format_date_value(value):
    if isinstance(value, dt.date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _escape_pdf_text(value):
    return html.escape(str(value))


def _fit_text(draw, text, font, max_width):
    text = str(text)
    if draw.textlength(text, font=font) <= max_width:
        return text

    ellipsis = "..."
    while text and draw.textlength(text + ellipsis, font=font) > max_width:
        text = text[:-1]
    return text + ellipsis if text else ellipsis


def _build_pdf_table(rows, font_name, column_widths):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    table = Table(rows, colWidths=column_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), PDF_FONT_SIZES["table"]),
                ("LEADING", (0, 0), (-1, -1), PDF_FONT_SIZES["table"] + 4),
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


def _register_pdf_font(font_path=None):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for candidate in resolve_font_candidates(font_path):
        if candidate.exists():
            pdfmetrics.registerFont(TTFont("ReportThai", str(candidate)))
            return "ReportThai"
    return "Helvetica"


def _load_image_font(size, font_path=None):
    from PIL import ImageFont

    for candidate in resolve_font_candidates(font_path):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _font_label(font_path):
    known_labels = {
        "THSarabunNew": "TH Sarabun New",
        "THSarabun": "TH Sarabun",
        "NotoSansThai-Regular": "Noto Sans Thai",
    }
    return known_labels.get(font_path.stem, font_path.stem)
