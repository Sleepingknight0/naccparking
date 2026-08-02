from __future__ import annotations

import unittest

from scripts.repair_misplaced_parking_rows import (
    MisplacedRow,
    build_repair_requests,
    find_misplaced_rows,
    verify_repair,
)


HEADER = ["วันที่ตรวจพบ", "อาคาร", "", ""] + [""] * 8 + ["date_key", "", "", ""]


def misplaced_row(date_key="2026-08-02", building="อาคาร 8", plate="กก 1234"):
    return [""] * 12 + [date_key, building, plate, "กรุงเทพมหานคร"]


class MisplacedParkingRepairTests(unittest.TestCase):
    def test_finds_rows_written_to_m_through_p(self):
        result = find_misplaced_rows([HEADER, misplaced_row()])

        self.assertEqual(
            result,
            [
                MisplacedRow(
                    2,
                    ("2026-08-02", "อาคาร 8", "กก 1234", "กรุงเทพมหานคร"),
                )
            ],
        )

    def test_refuses_rows_with_source_and_displaced_values(self):
        row = misplaced_row()
        row[:4] = ["2026-08-02", "อาคาร 8", "กก 1234", "กรุงเทพมหานคร"]

        with self.assertRaisesRegex(RuntimeError, "both A:D and M:P"):
            find_misplaced_rows([HEADER, row])

    def test_builds_one_batch_with_scoped_write_clear_and_formula_restore(self):
        rows = find_misplaced_rows([HEADER, misplaced_row(), misplaced_row("2026-08-01")])

        requests = build_repair_requests(sheet_id=42, row_count=20424, rows=rows)

        self.assertEqual(len(requests), 3)
        self.assertEqual(
            requests[0]["updateCells"]["range"],
            {
                "sheetId": 42,
                "startRowIndex": 1,
                "endRowIndex": 3,
                "startColumnIndex": 0,
                "endColumnIndex": 4,
            },
        )
        self.assertEqual(requests[1]["updateCells"]["range"]["startColumnIndex"], 12)
        formula = requests[2]["updateCells"]["rows"][0]["values"][0][
            "userEnteredValue"
        ]["formulaValue"]
        self.assertEqual(
            formula,
            '=ARRAYFORMULA(IF(A2:A20424="","",INT(A2:A20424)))',
        )

    def test_verification_accepts_repaired_rows_and_date_reformatting(self):
        before = find_misplaced_rows([HEADER, misplaced_row()])
        after = [
            HEADER,
            ["02/08/2026", "อาคาร 8", "กก 1234", "กรุงเทพมหานคร"]
            + [""] * 12,
        ]

        verify_repair(before, after)


if __name__ == "__main__":
    unittest.main()
