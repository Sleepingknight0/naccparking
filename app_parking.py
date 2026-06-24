import streamlit as st
from datetime import date, datetime, timedelta
import pandas as pd
import os
import json
import gspread
from google.oauth2.service_account import Credentials
import re
from dashboard.home_summary import render_home_mini_dashboard
from dashboard.theme import init_theme_state, set_theme_from_toggle, apply_theme_css
from parking_analysis import summarize_long_parkers
from report_generator import (
    build_detailed_report,
    get_report_font_options,
    get_report_period,
    make_report_filename,
    to_csv_bytes,
    to_summary_jpg_bytes,
    to_summary_pdf_bytes,
)

# การตั้งค่าหน้าจอเบื้องต้น
st.set_page_config(
    page_title="ระบบบันทึกรถค้างอาคาร", 
    page_icon="🏢", 
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# ----------------- THEME MANAGEMENT -----------------
init_theme_state()
apply_theme_css()

# สวิตช์เปิด/ปิด โหมดกลางคืน
col_space, col_toggle = st.columns([4, 1.5])
with col_toggle:
    st.toggle(
        "🌙 โหมดกลางคืน",
        key="dark_mode_toggle",
        value=(st.session_state.ui_theme == "dark"),
        on_change=set_theme_from_toggle,
    )


# ----------------- DATA MANAGEMENT (GOOGLE SHEETS) -----------------
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    if "gcp_service_account" not in st.secrets:
        st.error("❌ ไม่พบข้อมูล gcp_service_account ใน st.secrets")
        st.stop()
    
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    client = gspread.authorize(creds)
    
    if "spreadsheet_url" not in st.secrets:
        st.error("❌ ไม่พบข้อมูล spreadsheet_url ใน st.secrets")
        st.stop()
        
    spreadsheet = client.open_by_url(st.secrets["spreadsheet_url"])
    return spreadsheet.worksheet("RawData")

def load_data():
    columns = ["วันที่ตรวจพบ", "อาคาร", "ทะเบียนรถ", "จังหวัด"]
    st.session_state["load_data_error"] = None

    try:
        sheet = init_connection()
        values = sheet.get("A1:D")

        if len(values) > 1:
            return pd.DataFrame(values[1:], columns=columns)
        else:
            return pd.DataFrame(columns=columns)

    except Exception as e:
        st.session_state["load_data_error"] = str(e)
        st.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}")
        return pd.DataFrame(columns=columns)
        
BUILDINGS_FILE = "buildings.json"

def load_buildings():
    if not os.path.exists(BUILDINGS_FILE):
        default_buildings = ["อาคาร 1 (สำนักงานใหญ่)", "อาคาร 2 (พลาซ่า)", "อาคาร 3 (ลานจอดรถด้านหลัง)"]
        with open(BUILDINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_buildings, f, ensure_ascii=False)
        return default_buildings
    else:
        with open(BUILDINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

def save_buildings(buildings_list):
    with open(BUILDINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(buildings_list, f, ensure_ascii=False)

buildings_list = load_buildings()

def add_row_numbers(df):
    display_df = df.reset_index(drop=True).copy()
    display_df.insert(0, "ลำดับ", range(1, len(display_df) + 1))
    return display_df

def render_home_summary_placeholder(placeholder):
    home_summary_df = load_data()
    with placeholder.container():
        render_home_mini_dashboard(
            home_summary_df,
            buildings_list,
            error_message=st.session_state.get("load_data_error"),
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

def select_report_date(report_type):
    today = datetime.now().date()

    if report_type == "รายวัน":
        return st.date_input("เลือกวันที่", value=today)

    year_options = list(range(today.year - 3, today.year + 2))
    month_labels = [label for _, label in THAI_MONTHS]

    col_month, col_year = st.columns(2)
    with col_month:
        selected_month_label = st.selectbox(
            "เลือกเดือน",
            month_labels,
            index=today.month - 1,
            key=f"{report_type}_month",
        )
    with col_year:
        selected_year = st.selectbox(
            "เลือกปี",
            year_options,
            index=year_options.index(today.year),
            key=f"{report_type}_year",
        )

    selected_month = dict((label, month) for month, label in THAI_MONTHS)[selected_month_label]

    if report_type == "รายเดือน":
        return date(selected_year, selected_month, 1)

    week_options = build_week_options(selected_year, selected_month)
    default_week_index = find_default_week_index(week_options, today)
    selected_week = st.selectbox(
        "เลือกสัปดาห์",
        week_options,
        index=default_week_index,
        format_func=lambda week: week["label"],
    )
    return selected_week["start"]

def build_week_options(year, month):
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year, 12, 31)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    week_start = first_day - timedelta(days=first_day.weekday())
    weeks = []
    while week_start <= last_day:
        week_end = week_start + timedelta(days=6)
        weeks.append(
            {
                "start": week_start,
                "end": week_end,
                "label": f"{week_start:%d/%m/%Y} - {week_end:%d/%m/%Y}",
            }
        )
        week_start += timedelta(days=7)
    return weeks

def find_default_week_index(week_options, selected_date):
    for index, week in enumerate(week_options):
        if week["start"] <= selected_date <= week["end"]:
            return index
    return 0

# ----------------- ADMIN SETTINGS (SIDEBAR) -----------------
st.sidebar.markdown("## 🛠️ ตั้งค่าผู้ดูแลระบบ (Admin)")

st.sidebar.markdown("### 📈 รายงานและแดชบอร์ด")
if hasattr(st.sidebar, "page_link"):
    st.sidebar.page_link("pages/dashboard.py", label="› 📈 แดชบอร์ดภาพรวม")
elif hasattr(st, "switch_page"):
    if st.sidebar.button("› 📈 แดชบอร์ดภาพรวม", use_container_width=True):
        st.switch_page("pages/dashboard.py")
else:
    st.sidebar.caption("เปิดแดชบอร์ดจากเมนู Pages ของ Streamlit")
st.sidebar.markdown("---")
with st.sidebar.expander("📝 จัดการรายชื่ออาคาร", expanded=False):
    new_bldg = st.text_input("ชื่ออาคารใหม่:")
    if st.button("➕ เพิ่มอาคาร", use_container_width=True):
        if new_bldg and new_bldg not in buildings_list:
            buildings_list.append(new_bldg)
            save_buildings(buildings_list)
            st.success(f"เพิ่มอาคาร '{new_bldg}' สำเร็จ!")
            st.rerun()
        elif new_bldg in buildings_list:
            st.error("อาคารนี้มีอยู่ในระบบแล้ว")

    if buildings_list:
        bldg_to_delete = st.selectbox("เลือกอาคารที่ต้องการลบ:", buildings_list)
        if st.button("🗑️ ลบอาคาร", use_container_width=True):
            buildings_list.remove(bldg_to_delete)
            save_buildings(buildings_list)
            st.warning(f"ลบอาคาร '{bldg_to_delete}' สำเร็จ!")
            st.rerun()

with st.sidebar.expander("📊 ข้อมูลตาราง Google Sheets", expanded=False):
    st.write("ใส่รหัสผ่านเพื่อดูข้อมูลตาราง")
    admin_pwd = st.text_input("รหัสผ่าน (Password):", type="password")
    # ตั้งรหัสผ่านง่ายๆ ไว้ที่ 1234 (แอดมินเปลี่ยนเองได้ในโค้ด)
    if admin_pwd == "1234":
        try:
            df_display = load_data()
            
            tab1, tab2 = st.tabs(["📝 ข้อมูลทั้งหมด", "🚨 สรุปข้อมูลรถจอดนาน"])
            
            with tab1:
                current_date = datetime.now().strftime("%Y-%m-%d")

                df_today = df_display[df_display["วันที่ตรวจพบ"].astype(str) == current_date]

                st.dataframe(add_row_numbers(df_today), use_container_width=True, hide_index=True)
                st.success(f"โหลดข้อมูลประจำวันที่ {current_date} ทั้งหมด {len(df_today)} รายการ")
                
            with tab2:
                st.write("**วิเคราะห์รถที่จอดข้ามคืนสะสม**")
                days_threshold = st.number_input("กรองเฉพาะรถที่จอดสะสมตั้งแต่ (วัน):", min_value=1, value=7, step=1)
                
                if not df_display.empty:
                    long_parkers = summarize_long_parkers(df_display, days_threshold)
                    
                    if not long_parkers.empty:
                        st.dataframe(add_row_numbers(long_parkers), use_container_width=True, hide_index=True)
                        st.warning(f"พบรถที่จอดสะสม {days_threshold} วันขึ้นไป จำนวน {len(long_parkers)} คัน")
                    else:
                        st.success(f"ยังไม่พบรถที่จอดสะสมถึง {days_threshold} วัน 🎉")
                else:
                    st.info("ยังไม่มีข้อมูลในระบบ")
        except Exception as e:
            st.error(f"ไม่สามารถโหลดข้อมูลได้: {e}")
    elif admin_pwd != "":
        st.error("รหัสผ่านไม่ถูกต้อง")

with st.sidebar.expander("📥 โหลดรีพอร์ต", expanded=False):
    report_pwd = st.text_input("รหัสผ่านสำหรับโหลดรีพอร์ต:", type="password")
    if report_pwd == "1234":
        report_type = st.selectbox("ประเภทรายงาน", ["รายวัน", "รายสัปดาห์", "รายเดือน"])
        report_date = select_report_date(report_type)
        _, _, report_period_label = get_report_period(report_type, report_date)
        st.caption(f"ช่วงรายงาน: {report_period_label}")
        report_font_options = get_report_font_options()
        report_font_label = st.selectbox("ฟอนต์รายงาน", list(report_font_options.keys()))
        report_font_path = report_font_options[report_font_label]
        if report_font_path and not os.path.exists(report_font_path):
            st.caption(f"ยังไม่พบไฟล์ {report_font_path} ถ้าโหลดตอนนี้ระบบจะใช้ฟอนต์สำรอง")
        report_df = build_detailed_report(load_data(), report_type, report_date)

        if report_df.empty:
            st.info("ไม่พบข้อมูลในช่วงรายงานที่เลือก")
        else:
            st.caption(f"พบรถในรายงาน {len(report_df)} รายการ")
            st.download_button(
                "⬇️ ดาวน์โหลด CSV รายละเอียด",
                data=to_csv_bytes(report_df),
                file_name=make_report_filename(report_type, report_date, "csv"),
                mime="text/csv",
                use_container_width=True,
            )
            st.download_button(
                "⬇️ ดาวน์โหลด PDF สรุป",
                data=to_summary_pdf_bytes(
                    report_df,
                    report_df["ช่วงรายงาน"].iloc[0],
                    font_path=report_font_path,
                    report_type=report_type,
                ),
                file_name=make_report_filename(report_type, report_date, "pdf"),
                mime="application/pdf",
                use_container_width=True,
            )
            st.download_button(
                "⬇️ ดาวน์โหลด JPG สรุป",
                data=to_summary_jpg_bytes(
                    report_df,
                    report_df["ช่วงรายงาน"].iloc[0],
                    font_path=report_font_path,
                    report_type=report_type,
                ),
                file_name=make_report_filename(report_type, report_date, "jpg"),
                mime="image/jpeg",
                use_container_width=True,
            )
    elif report_pwd != "":
        st.error("รหัสผ่านไม่ถูกต้อง")


# ----------------- MAIN APP -----------------
if 'last_saved_plate' not in st.session_state:
    st.session_state.last_saved_plate = None
if 'last_saved_province' not in st.session_state:
    st.session_state.last_saved_province = None
if 'last_saved_row' not in st.session_state:
    st.session_state.last_saved_row = None

# ---- HEADER ----
st.markdown("""
<div class="header-container">
    <div class="header-title">🏢 ระบบบันทึกรถค้างอาคาร</div>
    <div class="header-subtitle">ส่วนงานรักษาความปลอดภัย (Security Department)</div>
</div>
""", unsafe_allow_html=True)

try:
    sheet = init_connection()
except Exception as e:
    st.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ Google Sheets: {e}")
    st.stop()

home_summary_placeholder = st.empty()
render_home_summary_placeholder(home_summary_placeholder)

# ---- FORM SECTION ----
st.markdown('<div class="section-title">📍 1. ข้อมูลสถานที่ตรวจพบ</div>', unsafe_allow_html=True)

if not buildings_list:
    st.error("ไม่มีรายชื่ออาคารในระบบ โปรดเพิ่มที่เมนู Admin (แถบด้านซ้าย)")
building = st.selectbox("อาคาร (Building)", buildings_list if buildings_list else [""])

st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">📝 2. ข้อมูลยานพาหนะ</div>', unsafe_allow_html=True)

col_plate, col_prov = st.columns([2, 1.5])
with col_plate:
    license_plate = st.text_input("ทะเบียนรถยนต์", placeholder="เช่น 9กข 1234").strip()
with col_prov:
    provinces_list = ["กรุงเทพมหานคร", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น", "จันทบุรี", "ฉะเชิงเทรา", "ชลบุรี", "ชัยนาท", "ชัยภูมิ", "ชุมพร", "เชียงราย", "เชียงใหม่", "ตรัง", "ตราด", "ตาก", "นครนายก", "นครปฐม", "นครพนม", "นครราชสีมา", "นครศรีธรรมราช", "นครสวรรค์", "นนทบุรี", "นราธิวาส", "น่าน", "บึงกาฬ", "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์", "ปราจีนบุรี", "ปัตตานี", "พระนครศรีอยุธยา", "พะเยา", "พังงา", "พัทลุง", "พิจิตร", "พิษณุโลก", "เพชรบุรี", "เพชรบูรณ์", "แพร่", "ภูเก็ต", "มหาสารคาม", "มุกดาหาร", "แม่ฮ่องสอน", "ยโสธร", "ยะลา", "ร้อยเอ็ด", "ระนอง", "ระยอง", "ราชบุรี", "ลพบุรี", "ลำปาง", "ลำพูน", "เลย", "ศรีสะเกษ", "สกลนคร", "สงขลา", "สตูล", "สมุทรปราการ", "สมุทรสงคราม", "สมุทรสาคร", "สระแก้ว", "สระบุรี", "สิงห์บุรี", "สุโขทัย", "สุพรรณบุรี", "สุราษฎร์ธานี", "สุรินทร์", "หนองคาย", "หนองบัวลำภู", "อ่างทอง", "อำนาจเจริญ", "อุดรธานี", "อุตรดิตถ์", "อุทัยธานี", "อุบลราชธานี"]
    province = st.selectbox("จังหวัด", provinces_list)

st.markdown("<br>", unsafe_allow_html=True)

# ---- ACTION BUTTONS ----
btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])

with btn_col2:
    if st.button("💾 บันทึกข้อมูลเข้าสู่ระบบ", type="primary", use_container_width=True):
        if license_plate == "":
            st.error("❌ กรุณากรอกทะเบียนรถก่อนบันทึกข้อมูลครับ")
        elif not building:
            st.error("❌ กรุณาเลือกอาคารก่อนบันทึกข้อมูลครับ")
        else:
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            try:
                # ตรวจสอบข้อมูลซ้ำของวันนี้
                records = sheet.get_all_values()
                is_duplicate = False
                for row in records:
                    if len(row) >= 4:
                        if row[0] == current_date and row[2] == license_plate and row[3] == province:
                            is_duplicate = True
                            break
                
                if is_duplicate:
                    st.error(f"⚠️ ข้อมูลซ้ำ! รถทะเบียน [{license_plate} {province}] ถูกบันทึกไปแล้วในวันนี้ครับ")
                else:
                    row_data = [current_date, building, license_plate, province]
                    res = sheet.append_row(row_data)
                    
                    # หา Row Index ที่เพิ่งถูกบันทึกลงไป เพื่อการลบที่แม่นยำ
                    updated_range = res.get('updates', {}).get('updatedRange', '')
                    if updated_range:
                        match = re.search(r'[A-Z]+(\d+)', updated_range)
                        if match:
                            st.session_state.last_saved_row = int(match.group(1))
                        else:
                            st.session_state.last_saved_row = None
                    else:
                        st.session_state.last_saved_row = None

                    st.session_state.last_saved_plate = license_plate
                    st.session_state.last_saved_province = province
                    st.success(f"✔️ บันทึกข้อมูลรถยนต์ [{license_plate} {province}] ลง Google Sheets สำเร็จ!")
                    render_home_summary_placeholder(home_summary_placeholder)
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดในการบันทึกข้อมูล: {e}")

if st.session_state.last_saved_plate:
    st.markdown("<br>", unsafe_allow_html=True)
    undo_col1, undo_col2, undo_col3 = st.columns([1.5, 1, 1.5])
    with undo_col2:
        if st.button("🗑️ ยกเลิกรายการล่าสุด", use_container_width=True):
            deleted_plate = st.session_state.last_saved_plate
            deleted_prov = st.session_state.last_saved_province
            row_to_delete = st.session_state.last_saved_row
            
            try:
                if row_to_delete:
                    sheet.delete_rows(row_to_delete)
                else:
                    # Fallback
                    records = sheet.get_all_values()
                    found_row = -1
                    for i in range(len(records)-1, -1, -1):
                        if len(records[i]) >= 4 and records[i][2] == deleted_plate and records[i][3] == deleted_prov:
                            found_row = i + 1
                            break
                    if found_row != -1:
                        sheet.delete_rows(found_row)
                    else:
                        st.warning("ไม่พบรายการดังกล่าวในระบบ")

                st.warning(f"ลบข้อมูลรถยนต์ [{deleted_plate} {deleted_prov}] ออกจาก Google Sheets เรียบร้อยแล้ว")
                st.session_state.last_saved_plate = None
                st.session_state.last_saved_province = None
                st.session_state.last_saved_row = None
                render_home_summary_placeholder(home_summary_placeholder)
                st.rerun()
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดในการลบข้อมูล: {e}")

# ---- END OF APP ----
