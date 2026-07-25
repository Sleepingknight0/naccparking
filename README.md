# ระบบบันทึกรถค้างอาคาร

Streamlit app used by the NACC security department (ส่วนงานรักษาความปลอดภัย) to log vehicles left parked in office buildings overnight, and to review which ones have been accumulating the most days.

Entries are appended to a Google Sheet, so there is no local database and the log stays readable by anyone the sheet is shared with.

## Features

- **Log a vehicle** — building, licence plate, and province (all 77 Thai provinces), stamped with the current date on save
- **Undo** — removes the row you just saved, falling back to a lookup by plate + province if the sheet has since shifted
- **Editable building list** — add or remove buildings from the sidebar; persisted to `buildings.json`
- **Admin table view** — password-gated, shows the full sheet inside the app
- **Light / dark theme** toggle, written back to `.streamlit/config.toml`

Sheet columns, in order: `วันที่ตรวจพบ` · `อาคาร` · `ทะเบียนรถ` · `จังหวัด`

## Requirements

- Python 3.9+
- A Google Cloud **service account** with the Google Sheets API enabled
- A Google Sheet shared with that service account's email as an **editor**

## Setup

```bash
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml`:

```toml
spreadsheet_url = "https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit"

[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "name@project.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

The app requests the `https://www.googleapis.com/auth/spreadsheets` scope and reads and writes the **first worksheet** (`sheet1`) of that spreadsheet. If either `gcp_service_account` or `spreadsheet_url` is missing, the app shows an error and stops.

## Run

```bash
streamlit run app_parking.py
```

## Admin panel

Expand **📊 ข้อมูลตาราง Google Sheets** in the sidebar and enter the password to load the full table into the app.

> **Note:** the admin password is currently hard-coded in `app_parking.py`. Move it into `st.secrets` before deploying this anywhere reachable from outside the office network.

## Layout

```text
app_parking.py     # entire app: theme, sidebar admin, form, Sheets I/O
buildings.json     # building list, rewritten when you add or remove one
requirements.txt   # streamlit, gspread, google-auth
.devcontainer/     # Codespaces / dev container config
```

## Notes

- `secrets.toml` contains a private key — keep it out of version control.
- The theme toggle rewrites `.streamlit/config.toml` at runtime, so that file changes as the app is used.
- `app_parking.py` also imports `pandas` and `toml`, which are not currently pinned in `requirements.txt`; install them if a fresh environment fails to start.

---

Forked from [captwcan/naccparking](https://github.com/captwcan/naccparking).
