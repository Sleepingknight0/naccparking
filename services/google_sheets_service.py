from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import gspread
import toml
from google.oauth2.service_account import Credentials


SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
PARKING_INPUT_RANGE = "A1:D"


@dataclass(frozen=True)
class GoogleSheetsSettings:
    spreadsheet_url: str
    service_account_info: dict[str, object]


def load_google_sheets_settings() -> GoogleSheetsSettings:
    """Load credentials without ever logging their contents."""
    spreadsheet_url = os.getenv("GOOGLE_SPREADSHEET_URL", "").strip()
    credentials_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    service_account_info: dict[str, object] = {}

    if credentials_json:
        service_account_info = json.loads(credentials_json)

    secrets_path = Path(".streamlit/secrets.toml")
    if secrets_path.exists() and (not spreadsheet_url or not service_account_info):
        secrets = toml.load(secrets_path)
        spreadsheet_url = spreadsheet_url or str(secrets.get("spreadsheet_url", "")).strip()
        service_account_info = service_account_info or dict(
            secrets.get("gcp_service_account", {})
        )

    if not spreadsheet_url:
        raise RuntimeError(
            "Missing GOOGLE_SPREADSHEET_URL (or spreadsheet_url in .streamlit/secrets.toml)"
        )
    if not service_account_info:
        raise RuntimeError(
            "Missing GOOGLE_SERVICE_ACCOUNT_JSON "
            "(or gcp_service_account in .streamlit/secrets.toml)"
        )
    return GoogleSheetsSettings(spreadsheet_url, service_account_info)


def connect_spreadsheet(settings: GoogleSheetsSettings | None = None):
    settings = settings or load_google_sheets_settings()
    credentials = Credentials.from_service_account_info(
        settings.service_account_info,
        scopes=[SHEETS_SCOPE],
    )
    return gspread.authorize(credentials).open_by_url(settings.spreadsheet_url)


def read_parking_values(worksheet) -> list[list[object]]:
    """Read only user-entered parking columns, excluding expensive formula columns."""
    return worksheet.get(PARKING_INPUT_RANGE)


def batch_delete_rows(worksheet, row_numbers: Iterable[int]) -> None:
    """Delete all requested rows with one Sheets batchUpdate request."""
    numbers = sorted(set(int(number) for number in row_numbers))
    if not numbers:
        return
    if numbers[0] <= 1:
        raise ValueError("Refusing to delete the header row")

    ranges: list[tuple[int, int]] = []
    start = end = numbers[0]
    for number in numbers[1:]:
        if number == end + 1:
            end = number
        else:
            ranges.append((start, end))
            start = end = number
    ranges.append((start, end))

    worksheet.spreadsheet.batch_update(
        {
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": worksheet.id,
                            "dimension": "ROWS",
                            "startIndex": start_row - 1,
                            "endIndex": end_row,
                        }
                    }
                }
                for start_row, end_row in reversed(ranges)
            ]
        }
    )


class GoogleSheetsService:
    def __init__(self, spreadsheet):
        self.spreadsheet = spreadsheet

    @classmethod
    def connect(cls) -> "GoogleSheetsService":
        return cls(connect_spreadsheet())

    def worksheet_names(self) -> set[str]:
        return {worksheet.title for worksheet in self.spreadsheet.worksheets()}

    def read_worksheets(self, names: Iterable[str]) -> dict[str, list[list[object]]]:
        names = list(names)
        if not names:
            return {}
        ranges = [f"'{_escape_sheet_name(name)}'" for name in names]
        response = self.spreadsheet.values_batch_get(
            ranges,
            params={
                "valueRenderOption": "FORMATTED_VALUE",
                "dateTimeRenderOption": "FORMATTED_STRING",
            }
        )
        value_ranges = response.get("valueRanges", [])
        return {
            name: value_ranges[index].get("values", [])
            if index < len(value_ranges)
            else []
            for index, name in enumerate(names)
        }

    def create_backup(self, source_name: str, backup_name: str) -> None:
        source = self.spreadsheet.worksheet(source_name)
        self.spreadsheet.duplicate_sheet(
            source.id,
            new_sheet_name=backup_name,
        )

    def ensure_worksheets(
        self,
        names: Iterable[str],
        *,
        rows: int,
        cols: int,
    ) -> dict[str, int]:
        existing = {worksheet.title: worksheet.id for worksheet in self.spreadsheet.worksheets()}
        missing = [name for name in names if name not in existing]
        if missing:
            response = self.spreadsheet.batch_update(
                {
                    "requests": [
                        {
                            "addSheet": {
                                "properties": {
                                    "title": name,
                                    "gridProperties": {
                                        "rowCount": max(rows, 2),
                                        "columnCount": max(cols, 4),
                                    },
                                }
                            }
                        }
                        for name in missing
                    ]
                }
            )
            replies = response.get("replies", [])
            for name, reply in zip(missing, replies):
                existing[name] = reply["addSheet"]["properties"]["sheetId"]
        return {name: existing[name] for name in names}

    def batch_write_values(self, writes: Iterable[tuple[str, int, list[list[object]]]]) -> None:
        data = []
        for sheet_name, start_row, rows in writes:
            if not rows:
                continue
            end_col = _column_letter(max(len(row) for row in rows))
            end_row = start_row + len(rows) - 1
            data.append(
                {
                    "range": (
                        f"'{_escape_sheet_name(sheet_name)}'!A{start_row}:{end_col}{end_row}"
                    ),
                    "majorDimension": "ROWS",
                    "values": rows,
                }
            )
        if data:
            self.spreadsheet.values_batch_update(
                body={"valueInputOption": "RAW", "data": data}
            )

    def copy_source_formats(
        self,
        source_name: str,
        destinations: dict[str, tuple[int, int]],
        *,
        column_count: int,
    ) -> None:
        if not destinations:
            return
        source_id = self.spreadsheet.worksheet(source_name).id
        sheet_ids = {
            worksheet.title: worksheet.id for worksheet in self.spreadsheet.worksheets()
        }
        requests = []
        for name, (data_start_row, data_row_count) in destinations.items():
            destination_id = sheet_ids[name]
            requests.append(
                _copy_format_request(source_id, destination_id, 0, 1, 0, 1, column_count)
            )
            if data_row_count:
                requests.append(
                    _copy_format_request(
                        source_id,
                        destination_id,
                        1,
                        2,
                        data_start_row - 1,
                        data_start_row - 1 + data_row_count,
                        column_count,
                    )
                )
        self.spreadsheet.batch_update({"requests": requests})

    def replace_source_columns(
        self,
        sheet_name: str,
        rows: list[list[object]],
        *,
        clear_through_row_count: int,
        column_count: int = 4,
    ) -> None:
        """Atomically replace data columns only; formulas/formatting remain untouched."""
        sheet_id = self.spreadsheet.worksheet(sheet_name).id
        target_count = max(len(rows), clear_through_row_count)
        update_rows = []
        for index in range(target_count):
            source_row = rows[index] if index < len(rows) else []
            update_rows.append(
                {
                    "values": [
                        {"userEnteredValue": _user_entered_value(source_row[col])}
                        if col < len(source_row) and source_row[col] not in (None, "")
                        else {}
                        for col in range(column_count)
                    ]
                }
            )
        if not update_rows:
            return
        self.spreadsheet.batch_update(
            {
                "requests": [
                    {
                        "updateCells": {
                            "start": {
                                "sheetId": sheet_id,
                                "rowIndex": 1,
                                "columnIndex": 0,
                            },
                            "rows": update_rows,
                            "fields": "userEnteredValue",
                        }
                    }
                ]
            }
        )


def _copy_format_request(
    source_id: int,
    destination_id: int,
    source_start_row: int,
    source_end_row: int,
    destination_start_row: int,
    destination_end_row: int,
    column_count: int,
) -> dict[str, object]:
    return {
        "copyPaste": {
            "source": {
                "sheetId": source_id,
                "startRowIndex": source_start_row,
                "endRowIndex": source_end_row,
                "startColumnIndex": 0,
                "endColumnIndex": column_count,
            },
            "destination": {
                "sheetId": destination_id,
                "startRowIndex": destination_start_row,
                "endRowIndex": destination_end_row,
                "startColumnIndex": 0,
                "endColumnIndex": column_count,
            },
            "pasteType": "PASTE_FORMAT",
            "pasteOrientation": "NORMAL",
        }
    }


def _user_entered_value(value: object) -> dict[str, object]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, (int, float)):
        return {"numberValue": value}
    return {"stringValue": str(value)}


def _escape_sheet_name(name: str) -> str:
    return name.replace("'", "''")


def _column_letter(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result
