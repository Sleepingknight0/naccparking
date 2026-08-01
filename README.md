# NACC Overnight Parking Log

A Streamlit application for recording vehicles that remain inside NACC office buildings overnight and reviewing repeated or long-running parking records.

The interface is intended for security staff. Operational records are stored in Google Sheets, while the local repository holds the application and editable building list.

## Overview

Each submission records the observation date, building, licence plate, and Thai province. The application writes new rows to the first worksheet of the configured spreadsheet.

This repository is a fork of [`captwcan/naccparking`](https://github.com/captwcan/naccparking).

## Key capabilities

- Record overnight vehicles with an automatic observation date.
- Select from all 77 Thai provinces.
- Undo the most recent submission safely.
- Add or remove buildings through the sidebar.
- Persist the building list in `buildings.json`.
- Review the complete worksheet through a password-protected admin panel.
- Switch between light and dark Streamlit themes.

## Data model

The first worksheet must contain these columns in this order:

| Position | Field            | Description                                      |
| -------: | ---------------- | ------------------------------------------------ |
|        1 | Observation date | Date on which the vehicle was found              |
|        2 | Building         | Selected NACC building or parking area           |
|        3 | Licence plate    | Vehicle registration text entered by staff       |
|        4 | Province         | Thai province selected from the application list |

The repository does not include a local database. Access control and record retention therefore depend on the configured Google Sheet.

## Requirements

- Python 3.11.
- A Google Cloud service account with the Google Sheets API enabled.
- A Google Sheet shared with the service account as an editor.

The development container is configured for Python 3.11 and Streamlit port `8501`.

## Installation

Create and activate a virtual environment, then install the dependencies:

```bash
python -m venv .venv
```

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The application also imports `pandas` and `toml`. They are normally installed through Streamlit, but should be declared directly if the dependency file is hardened later.

## Google Sheets configuration

Create `.streamlit/secrets.toml` and add the spreadsheet URL plus the service account credentials:

```toml
spreadsheet_url = "https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit"

[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "service-account@project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "your-certificate-url"
```

The application requests the `spreadsheets` scope and opens `sheet1`. It stops with an error when either `spreadsheet_url` or `gcp_service_account` is missing.

## Run locally

Start Streamlit from the repository root:

```bash
streamlit run app_parking.py
```

Open the local URL reported by Streamlit, normally `http://localhost:8501`.

## Run in GitHub Codespaces

Create a Codespace from the repository. The development container installs `requirements.txt`, starts Streamlit on port `8501`, and opens a preview automatically.

Add `.streamlit/secrets.toml` inside the Codespace before attempting to connect to Google Sheets.

## Administration

The sidebar contains controls for the building registry and the Google Sheets table view. Building changes rewrite `buildings.json` in the running environment.

The current admin password is hard-coded in `app_parking.py`. Move it to `st.secrets`, use a strong value, and add proper authentication before exposing the application outside a trusted network.

## Repository structure

```text
.
|-- app_parking.py              # Streamlit interface and Google Sheets workflow
|-- buildings.json              # Editable building registry
|-- requirements.txt            # Direct Python dependencies
|-- .devcontainer/
|   `-- devcontainer.json       # Codespaces configuration
`-- README.md                   # Project documentation
```

## Security and data handling

- Never commit `.streamlit/secrets.toml` or a service account private key.
- Limit spreadsheet sharing to authorized operational staff.
- Replace the hard-coded admin password before public deployment.
- Treat licence plates and observation records as operationally sensitive data.
- Review access logs and spreadsheet permissions regularly.
- Expect `.streamlit/config.toml` to change when users switch themes.

## Known limitations

- The application uses the first worksheet only.
- The building registry is stored on the local filesystem and may not persist on ephemeral hosting.
- The admin panel uses a shared password instead of identity-based access control.
- No automated test suite is included.

## License

The upstream repository does not publish a licence. This fork cannot grant reuse rights that the upstream author has not provided.

Contact the upstream author before copying, modifying, or redistributing the code.
