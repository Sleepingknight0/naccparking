from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.archive_service import parse_parking_datetime
from services.google_sheets_service import connect_spreadsheet


BANGKOK = ZoneInfo("Asia/Bangkok")
SOURCE_SHEET = "RawData"
SOURCE_RANGE = "A1:P"
INPUT_START_COLUMN = 0
DISPLACED_START_COLUMN = 12
INPUT_COLUMN_COUNT = 4


@dataclass(frozen=True)
class MisplacedRow:
    row_number: int
    values: tuple[object, object, object, object]


def _slice(row: list[object], start: int, count: int) -> list[object]:
    padded = list(row) + [""] * max(0, start + count - len(row))
    return padded[start : start + count]


def find_misplaced_rows(values: list[list[object]]) -> list[MisplacedRow]:
    misplaced: list[MisplacedRow] = []
    for row_number, row in enumerate(values[1:], start=2):
        source = _slice(row, INPUT_START_COLUMN, INPUT_COLUMN_COUNT)
        displaced = _slice(row, DISPLACED_START_COLUMN, INPUT_COLUMN_COUNT)
        has_displaced_record = all(str(value).strip() for value in displaced[:3])
        if not has_displaced_record:
            continue
        if any(str(value).strip() for value in source):
            raise RuntimeError(
                f"Row {row_number} has values in both A:D and M:P; refusing automatic repair"
            )
        misplaced.append(MisplacedRow(row_number, tuple(displaced)))
    return misplaced


def _contiguous_groups(rows: Iterable[MisplacedRow]) -> list[list[MisplacedRow]]:
    groups: list[list[MisplacedRow]] = []
    for row in sorted(rows, key=lambda item: item.row_number):
        if not groups or row.row_number != groups[-1][-1].row_number + 1:
            groups.append([row])
        else:
            groups[-1].append(row)
    return groups


def _string_cell(value: object) -> dict[str, object]:
    return {"userEnteredValue": {"stringValue": str(value)}}


def build_repair_requests(
    sheet_id: int,
    row_count: int,
    rows: list[MisplacedRow],
) -> list[dict[str, object]]:
    requests: list[dict[str, object]] = []
    for group in _contiguous_groups(rows):
        start_index = group[0].row_number - 1
        end_index = group[-1].row_number
        requests.append(
            {
                "updateCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_index,
                        "endRowIndex": end_index,
                        "startColumnIndex": INPUT_START_COLUMN,
                        "endColumnIndex": INPUT_START_COLUMN + INPUT_COLUMN_COUNT,
                    },
                    "rows": [
                        {"values": [_string_cell(value) for value in row.values]}
                        for row in group
                    ],
                    "fields": "userEnteredValue",
                }
            }
        )
        requests.append(
            {
                "updateCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_index,
                        "endRowIndex": end_index,
                        "startColumnIndex": DISPLACED_START_COLUMN,
                        "endColumnIndex": DISPLACED_START_COLUMN + INPUT_COLUMN_COUNT,
                    },
                    "rows": [
                        {"values": [{} for _ in range(INPUT_COLUMN_COUNT)]}
                        for _ in group
                    ],
                    "fields": "userEnteredValue",
                }
            }
        )

    formula = f'=ARRAYFORMULA(IF(A2:A{row_count}="","",INT(A2:A{row_count})))'
    requests.append(
        {
            "updateCells": {
                "start": {
                    "sheetId": sheet_id,
                    "rowIndex": 1,
                    "columnIndex": DISPLACED_START_COLUMN,
                },
                "rows": [
                    {"values": [{"userEnteredValue": {"formulaValue": formula}}]}
                ],
                "fields": "userEnteredValue",
            }
        }
    )
    requests.append(
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "endRowIndex": row_count,
                    "startColumnIndex": DISPLACED_START_COLUMN,
                    "endColumnIndex": DISPLACED_START_COLUMN + 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {"type": "DATE", "pattern": "d/M/yyyy"}
                    }
                },
                "fields": "userEnteredFormat.numberFormat",
            }
        }
    )
    return requests


def _fingerprint(values: Iterable[object]) -> tuple[str, str, str, str]:
    values = list(values)
    parsed = parse_parking_datetime(values[0])
    if parsed is None:
        raise RuntimeError(f"Invalid date encountered during repair verification: {values[0]!r}")
    return (
        parsed.date().isoformat(),
        str(values[1]).strip(),
        str(values[2]).strip(),
        str(values[3]).strip(),
    )


def verify_repair(
    before: list[MisplacedRow],
    after_values: list[list[object]],
) -> None:
    remaining = find_misplaced_rows(after_values)
    if remaining:
        raise RuntimeError(f"Verification failed: {len(remaining)} displaced rows remain")

    expected = Counter(_fingerprint(row.values) for row in before)
    actual = Counter(
        _fingerprint(_slice(row, INPUT_START_COLUMN, INPUT_COLUMN_COUNT))
        for row in after_values[1:]
        if all(str(value).strip() for value in _slice(row, 0, 3))
    )
    missing = expected - actual
    if missing:
        raise RuntimeError(
            f"Verification failed: {sum(missing.values())} repaired rows are missing from A:D"
        )


def _rollback_request(source_id: int, destination_id: int, rows: int) -> dict[str, object]:
    return {
        "copyPaste": {
            "source": {
                "sheetId": source_id,
                "startRowIndex": 0,
                "endRowIndex": rows,
                "startColumnIndex": 0,
                "endColumnIndex": 16,
            },
            "destination": {
                "sheetId": destination_id,
                "startRowIndex": 0,
                "endRowIndex": rows,
                "startColumnIndex": 0,
                "endColumnIndex": 16,
            },
            "pasteType": "PASTE_NORMAL",
            "pasteOrientation": "NORMAL",
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    logger = logging.getLogger("repair-misplaced-parking-rows")
    spreadsheet = connect_spreadsheet()
    worksheet = spreadsheet.worksheet(SOURCE_SHEET)
    values = worksheet.get(SOURCE_RANGE)
    misplaced = find_misplaced_rows(values)
    counts = Counter(_fingerprint(row.values)[0] for row in misplaced)

    logger.info("Source sheet: %s", SOURCE_SHEET)
    logger.info("Misplaced rows found: %d", len(misplaced))
    for date_key, count in sorted(counts.items()):
        logger.info("%s: %d rows", date_key, count)

    if args.dry_run:
        logger.info("No data was modified.")
        return 0
    if not misplaced:
        logger.info("No misplaced rows remain; restoring date_key formula and format only")
    if not args.yes:
        answer = input("Create backup and repair these rows? [y/N]: ").strip().lower()
        if answer not in {"y", "yes"}:
            logger.info("Cancelled. No data was modified.")
            return 0

    timestamp = datetime.now(BANGKOK).strftime("%Y%m%d_%H%M%S")
    backup_name = f"Backup_RawData_Repair_{timestamp}"
    backup = spreadsheet.duplicate_sheet(worksheet.id, new_sheet_name=backup_name)
    logger.info("Backup created: %s", backup_name)

    try:
        spreadsheet.batch_update(
            {"requests": build_repair_requests(worksheet.id, worksheet.row_count, misplaced)}
        )
        verify_repair(misplaced, worksheet.get(SOURCE_RANGE))
    except Exception:
        logger.exception("Repair failed; restoring RawData from %s", backup_name)
        spreadsheet.batch_update(
            {
                "requests": [
                    _rollback_request(backup.id, worksheet.id, worksheet.row_count)
                ]
            }
        )
        raise

    logger.info("Verification passed")
    logger.info("Repaired %d rows into A:D", len(misplaced))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
