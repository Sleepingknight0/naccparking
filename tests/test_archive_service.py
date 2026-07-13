from __future__ import annotations

import logging
import unittest
from copy import deepcopy
from datetime import datetime
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from services.archive_service import (
    ArchiveMigration,
    build_archive_plan,
    parse_parking_datetime,
    rows_to_append,
)
from services.google_sheets_service import (
    GoogleSheetsService,
    batch_delete_rows,
    read_parking_values,
)


NOW = datetime(2026, 7, 13, 12, 0, tzinfo=ZoneInfo("Asia/Bangkok"))
HEADER = ["วันที่ตรวจพบ", "อาคาร", "ทะเบียนรถ", "จังหวัด"]


def row(value: str, building: str = "A", plate: str = "กก1", province: str = "กทม"):
    return [value, building, plate, province]


class FakeSheets:
    def __init__(self, values: dict[str, list[list[object]]]):
        self.values = deepcopy(values)
        self.fail_write = False
        self.fail_backup = False
        self.replace_calls = 0

    def read_worksheets(self, names):
        return {name: deepcopy(self.values.get(name, [])) for name in names}

    def worksheet_names(self):
        return set(self.values)

    def create_backup(self, source_name, backup_name):
        if self.fail_backup:
            raise RuntimeError("backup API failed")
        self.values[backup_name] = deepcopy(self.values[source_name])

    def ensure_worksheets(self, names, *, rows, cols):
        for index, name in enumerate(names, start=100):
            self.values.setdefault(name, [])
        return {name: index for index, name in enumerate(names, start=100)}

    def batch_write_values(self, writes):
        if self.fail_write:
            raise RuntimeError("archive API failed")
        for name, start_row, rows in writes:
            target = self.values.setdefault(name, [])
            while len(target) < start_row - 1:
                target.append([])
            for offset, value in enumerate(rows):
                index = start_row - 1 + offset
                if index < len(target):
                    target[index] = deepcopy(value)
                else:
                    target.append(deepcopy(value))

    def copy_source_formats(self, *args, **kwargs):
        return None

    def replace_source_columns(
        self, sheet_name, rows, *, clear_through_row_count, column_count=4
    ):
        self.replace_calls += 1
        header = self.values[sheet_name][0]
        self.values[sheet_name] = [header] + deepcopy(rows)


class ArchivePlanningTests(unittest.TestCase):
    def test_current_month_is_not_moved(self):
        plan = build_archive_plan([HEADER, row("2026-07-01")], now=NOW)
        self.assertEqual(plan.archive_total, 0)
        self.assertEqual(plan.retained_rows, [row("2026-07-01")])

    def test_previous_month_moves_to_correct_sheet(self):
        plan = build_archive_plan([HEADER, row("2026-06-30")], now=NOW)
        self.assertEqual(plan.archive_rows, {"Archive_2026_06": [row("2026-06-30")]})

    def test_multiple_months_are_split(self):
        plan = build_archive_plan(
            [HEADER, row("2026-04-01"), row("15/05/2026"), row("2026-06-01")],
            now=NOW,
        )
        self.assertEqual(
            list(plan.archive_rows),
            ["Archive_2026_04", "Archive_2026_05", "Archive_2026_06"],
        )

    def test_invalid_date_is_retained_and_reported(self):
        invalid = row("not-a-date")
        plan = build_archive_plan([HEADER, invalid], now=NOW)
        self.assertEqual(plan.retained_rows, [invalid])
        self.assertEqual(plan.invalid_dates[0].sheet_row, 2)

    def test_rerun_does_not_append_existing_rows(self):
        source = [row("2026-06-01")]
        self.assertEqual(rows_to_append(source, source), [])

    def test_existing_archive_gets_only_missing_rows(self):
        existing = [row("2026-06-01")]
        missing = row("2026-06-02")
        self.assertEqual(rows_to_append(existing + [missing], existing), [missing])

    def test_preexisting_duplicate_multiplicity_is_preserved_idempotently(self):
        duplicate = row("2026-06-01")
        self.assertEqual(rows_to_append([duplicate, duplicate], [duplicate]), [duplicate])
        self.assertEqual(rows_to_append([duplicate, duplicate], [duplicate, duplicate]), [])

    def test_header_only(self):
        plan = build_archive_plan([HEADER], now=NOW)
        self.assertEqual(plan.source_total, 0)

    def test_empty_raw_data(self):
        plan = build_archive_plan([], now=NOW)
        self.assertEqual(plan.source_total, 0)
        self.assertEqual(plan.header, [])

    def test_blank_row_between_data_is_reported(self):
        plan = build_archive_plan(
            [HEADER, row("2026-06-01"), ["", "", "", ""], row("2026-07-01")],
            now=NOW,
        )
        self.assertEqual(plan.blank_rows, [3])
        self.assertEqual(plan.source_total, 2)

    def test_supported_date_values(self):
        for value in (
            "13/07/2026",
            "13/07/2026 01:02:03",
            "2026-07-13",
            "2026-07-13 01:02:03",
            datetime(2026, 7, 13),
        ):
            self.assertEqual(parse_parking_datetime(value).date().isoformat(), "2026-07-13")


class GoogleSheetsServiceTests(unittest.TestCase):
    def test_parking_read_excludes_formula_columns(self):
        worksheet = Mock()
        worksheet.get.return_value = [["header"]]

        result = read_parking_values(worksheet)

        self.assertEqual(result, [["header"]])
        worksheet.get.assert_called_once_with("A1:D")

    def test_delete_rows_uses_one_batch_in_descending_ranges(self):
        worksheet = Mock()
        worksheet.id = 42

        batch_delete_rows(worksheet, [5, 6, 9])

        worksheet.spreadsheet.batch_update.assert_called_once_with(
            {
                "requests": [
                    {
                        "deleteDimension": {
                            "range": {
                                "sheetId": 42,
                                "dimension": "ROWS",
                                "startIndex": 8,
                                "endIndex": 9,
                            }
                        }
                    },
                    {
                        "deleteDimension": {
                            "range": {
                                "sheetId": 42,
                                "dimension": "ROWS",
                                "startIndex": 4,
                                "endIndex": 6,
                            }
                        }
                    },
                ]
            }
        )

    def test_batch_read_passes_ranges_without_row_by_row_requests(self):
        spreadsheet = Mock()
        spreadsheet.values_batch_get.return_value = {
            "valueRanges": [{"values": [["header"]]}, {"values": [["archive"]]}]
        }

        result = GoogleSheetsService(spreadsheet).read_worksheets(
            ["RawData", "Archive_2026_06"]
        )

        self.assertEqual(result["RawData"], [["header"]])
        spreadsheet.values_batch_get.assert_called_once_with(
            ["'RawData'", "'Archive_2026_06'"],
            params={
                "valueRenderOption": "FORMATTED_VALUE",
                "dateTimeRenderOption": "FORMATTED_STRING",
            },
        )


class ArchiveExecutionTests(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("archive-test")
        self.logger.handlers.clear()
        self.logger.addHandler(logging.NullHandler())

    def test_backup_succeeds_but_archive_write_failure_keeps_raw_data(self):
        original = [HEADER, row("2026-06-01"), row("2026-07-01")]
        sheets = FakeSheets({"RawData": original})
        plan = build_archive_plan(original, now=NOW)
        sheets.fail_write = True

        with self.assertRaisesRegex(RuntimeError, "archive API failed"):
            ArchiveMigration(sheets, self.logger).execute(plan, now=NOW)

        self.assertEqual(sheets.values["RawData"], original)
        self.assertTrue(any(name.startswith("Backup_RawData_") for name in sheets.values))
        self.assertEqual(sheets.replace_calls, 0)

    def test_backup_api_failure_does_not_write_archive_or_raw_data(self):
        original = [HEADER, row("2026-06-01")]
        sheets = FakeSheets({"RawData": original})
        sheets.fail_backup = True

        with self.assertRaisesRegex(RuntimeError, "backup API failed"):
            ArchiveMigration(sheets, self.logger).execute(
                build_archive_plan(original, now=NOW), now=NOW
            )

        self.assertEqual(sheets.values, {"RawData": original})

    def test_count_and_content_are_verified_before_source_update(self):
        old = row("2026-06-01")
        current = row("2026-07-01")
        original = [HEADER, old, current]
        sheets = FakeSheets({"RawData": original})

        result = ArchiveMigration(sheets, self.logger).execute(
            build_archive_plan(original, now=NOW), now=NOW
        )

        self.assertEqual(result.appended_rows, 1)
        self.assertEqual(result.retained_rows, 1)
        self.assertEqual(sheets.values["RawData"], [HEADER, current])
        self.assertEqual(sheets.values["Archive_2026_06"], [HEADER, old])

    def test_existing_archive_makes_execute_retry_safe(self):
        old = row("2026-06-01")
        current = row("2026-07-01")
        original = [HEADER, old, current]
        sheets = FakeSheets(
            {"RawData": original, "Archive_2026_06": [HEADER, old]}
        )

        result = ArchiveMigration(sheets, self.logger).execute(
            build_archive_plan(original, now=NOW), now=NOW
        )

        self.assertEqual(result.appended_rows, 0)
        self.assertEqual(result.already_archived_rows, 1)
        self.assertEqual(sheets.values["Archive_2026_06"], [HEADER, old])
        self.assertEqual(sheets.values["RawData"], [HEADER, current])


if __name__ == "__main__":
    unittest.main()
