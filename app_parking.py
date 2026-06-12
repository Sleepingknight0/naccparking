import streamlit as st
from datetime import datetime
import pandas as pd
import os
import toml
import json
import gspread
from google.oauth2.service_account import Credentials
import re

# การตั้งค่าหน้าจอเบื้องต้น
st.set_page_config(
    page_title="ระบบบันทึกรถค้างอาคาร", 
    page_icon="🏢", 
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# ----------------- THEME MANAGEMENT -----------------
CONFIG_PATH = ".streamlit/config.toml"

def get_current_theme():
    """อ่านค่า Theme ปัจจุบันจาก config.toml"""
    if os.path.exists(CONFIG_PATH):
        try:
            config = toml.load(CONFIG_PATH)
            return config.get("theme", {}).get("base", "light")
        except:
            return "light"
    return "light"

def set_theme(theme_base):
    """เขียนค่า Theme ใหม่ลงไปใน config.toml เพื่อบังคับเปลี่ยนธีมทั้งระบบ"""
    if not os.path.exists(".streamlit"):
        os.makedirs(".streamlit")
    
    config = {}
    if os.path.exists(CONFIG_PATH):
        try:
            config = toml.load(CONFIG_PATH)
        except:
            pass
            
    if "theme" not in config:
        config["theme"] = {}
        
    if config["theme"].get("base") == theme_base:
        return
        
    config["theme"]["base"] = theme_base
    config["theme"]["primaryColor"] = "#2c5364"
    config["theme"]["font"] = "sans serif"
    
    with open(CONFIG_PATH, "w") as f:
        toml.dump(config, f)
        
current_theme = get_current_theme()
is_dark = True if current_theme == "dark" else False

# สวิตช์เปิด/ปิด โหมดกลางคืน
col_space, col_toggle = st.columns([4, 1.5])
with col_toggle:
    dark_mode_toggle = st.toggle("🌙 โหมดกลางคืน", value=is_dark)
    if dark_mode_toggle != is_dark:
        if dark_mode_toggle:
            set_theme("dark")
        else:
            set_theme("light")
        st.rerun()

# ----------------- CUSTOM CSS -----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Kanit', sans-serif !important;
    }
    
    .header-container {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        padding: 2.5rem 2rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.15);
        margin-bottom: 2rem;
        margin-top: 0.5rem;
    }
    .header-title {
        font-size: 2.2rem;
        font-weight: 600;
        margin: 0;
        letter-spacing: 0.5px;
    }
    .header-subtitle {
        font-size: 1.1rem;
        font-weight: 300;
        color: #e0e0e0;
        margin-top: 0.5rem;
    }

    .section-title {
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e2e8f0;
    }
    
    div.stButton > button:first-child {
        font-family: 'Kanit', sans-serif;
        font-size: 1.1rem;
        font-weight: 500;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
    }
</style>
""", unsafe_allow_html=True)

if is_dark:
    st.markdown("""
    <style>
        .header-container {
            background: linear-gradient(135deg, #1c2b33 0%, #15262c 50%, #0d171a 100%);
            border: 1px solid #2d3748;
        }
        .section-title {
            color: var(--text-color) !important;
            border-bottom: 2px solid #4a5568;
        }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
        .section-title {
            color: var(--text-color) !important;
        }
    </style>
    """, unsafe_allow_html=True)


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
        
    return client.open_by_url(st.secrets["spreadsheet_url"]).sheet1

def load_data():
    try:
        sheet = init_connection()
        records = sheet.get_all_records()
        if records:
            return pd.DataFrame(records)
        else:
            return pd.DataFrame(columns=["วันที่ตรวจพบ", "อาคาร", "ทะเบียนรถ", "จังหวัด"])
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}")
        return pd.DataFrame(columns=["วันที่ตรวจพบ", "อาคาร", "ทะเบียนรถ", "จังหวัด"])

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

# ----------------- ADMIN SETTINGS (SIDEBAR) -----------------
st.sidebar.markdown("## 🛠️ ตั้งค่าผู้ดูแลระบบ (Admin)")
st.sidebar.write("ส่วนสำหรับเพิ่ม/ลด รายชื่ออาคาร")

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
            
    st.markdown("---")
    if buildings_list:
        bldg_to_delete = st.selectbox("เลือกอาคารที่ต้องการลบ:", buildings_list)
        if st.button("🗑️ ลบอาคาร", use_container_width=True):
            buildings_list.remove(bldg_to_delete)
            save_buildings(buildings_list)
            st.warning(f"ลบอาคาร '{bldg_to_delete}' สำเร็จ!")
            st.rerun()

st.sidebar.markdown("---")
with st.sidebar.expander("📊 ข้อมูลตาราง Google Sheets", expanded=False):
    st.write("ใส่รหัสผ่านเพื่อดูข้อมูลตาราง")
    admin_pwd = st.text_input("รหัสผ่าน (Password):", type="password")
    # ตั้งรหัสผ่านง่ายๆ ไว้ที่ 1234 (แอดมินเปลี่ยนเองได้ในโค้ด)
    if admin_pwd == "1234":
        try:
            df_display = load_data()
            
            tab1, tab2 = st.tabs(["📝 ข้อมูลทั้งหมด", "🚨 สรุปข้อมูลรถจอดนาน"])
            
            with tab1:
                st.dataframe(df_display, use_container_width=True)
                st.success(f"โหลดข้อมูลสำเร็จทั้งหมด {len(df_display)} รายการ")
                
            with tab2:
                st.write("**วิเคราะห์รถที่จอดข้ามคืนสะสม**")
                days_threshold = st.number_input("กรองเฉพาะรถที่จอดสะสมตั้งแต่ (วัน):", min_value=1, value=7, step=1)
                
                if not df_display.empty:
                    # จัดกลุ่มตามทะเบียน จังหวัด และอาคารเพื่อนับจำนวนวัน
                    summary = df_display.groupby(['ทะเบียนรถ', 'จังหวัด', 'อาคาร']).size().reset_index(name='จำนวนวันที่จอดสะสม (วัน)')
                    
                    # กรองเฉพาะที่จอดเกินวันที่กำหนด
                    long_parkers = summary[summary['จำนวนวันที่จอดสะสม (วัน)'] >= days_threshold]
                    
                    # เรียงจากจอดนานสุดไปน้อยสุด
                    long_parkers = long_parkers.sort_values(by='จำนวนวันที่จอดสะสม (วัน)', ascending=False).reset_index(drop=True)
                    
                    if not long_parkers.empty:
                        st.dataframe(long_parkers, use_container_width=True)
                        st.warning(f"พบรถที่จอดสะสม {days_threshold} วันขึ้นไป จำนวน {len(long_parkers)} คัน")
                    else:
                        st.success(f"ยังไม่พบรถที่จอดสะสมถึง {days_threshold} วัน 🎉")
                else:
                    st.info("ยังไม่มีข้อมูลในระบบ")
        except Exception as e:
            st.error(f"ไม่สามารถโหลดข้อมูลได้: {e}")
    elif admin_pwd != "":
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
                st.rerun()
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดในการลบข้อมูล: {e}")

# ---- END OF APP ----
