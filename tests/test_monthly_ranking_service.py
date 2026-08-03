from __future__ import annotations

import logging
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from services.monthly_ranking_service import (
    MonthlyRankingPlan,
    MonthlyRankingRepair,
    MonthStats,
    available_months,
    build_month_stats,
    build_update_requests,
    first_or_last_date_formula,
    monthly_table_formula,
    source_sheet_for_month,
    verify_summary_values,
)

BANGKOK = ZoneInfo("Asia/Bangkok")


def parking_row(day: str, key: str, building: str = "อาคาร 4") -> list[object]:
    plate, province = key.split("|", 1)
    return [day, building, plate, province, plate, key]


class FakeWorksheet:
    def __init__(self, title: str, sheet_id: int):
        self.title = title
        self.id = sheet_id
        self.row_count = 1000
        self.col_count = 17


class LoadPlanSpreadsheet:
    def __init__(self, *, old_formula: bool = False):
        self.old_formula = old_formula
        self.items = {
            "RawData": FakeWorksheet("RawData", 1),
            "Archive_2026_07": FakeWorksheet("Archive_2026_07", 2),
            "MonthlyRanking": FakeWorksheet("MonthlyRanking", 3),
        }

    def worksheets(self):
        return list(self.items.values())

    def values_batch_get(self, ranges, params=None):
        del params
        if ranges == ["'RawData'!A2:F", "'Archive_2026_07'!A2:F"]:
            return {
                "valueRanges": [
                    {"values": [parking_row("1/8/2026", "กก1|กรุงเทพมหานคร")]},
                    {"values": [parking_row("1/7/2026", "กก2|กรุงเทพมหานคร")]},
                ]
            }
        formula = "=OLD" if self.old_formula else monthly_table_formula()
        values = [
            [[46235]],
            [[first_or_last_date_formula("MIN")]],
            [[first_or_last_date_formula("MAX")]],
            [['=IF(OR(D1="",F1=""),"",F1-D1+1)']],
            [['=IF(H1="","",ROUNDUP(H1*80%,0))']],
            [[formula]],
            [[[46236], [46236], [46205]]][0],
            [["ทั้งหมด"]],
        ]
        return {"valueRanges": [{"values": value} for value in values]}


class FailingWriteSpreadsheet:
    def __init__(self):
        self.summary = FakeWorksheet("MonthlyRanking", 10)
        self.backup = FakeWorksheet("backup", 11)
        self.batch_calls = []
        self.duplicates = []

    def worksheet(self, title):
        if title == "MonthlyRanking":
            return self.summary
        return self.backup

    def duplicate_sheet(self, sheet_id, new_sheet_name):
        self.duplicates.append((sheet_id, new_sheet_name))
        return self.backup

    def batch_update(self, payload):
        self.batch_calls.append(payload)
        if len(self.batch_calls) == 1:
            raise RuntimeError("simulated Google API failure")


class MonthlyRankingServiceTests(unittest.TestCase):
    def test_available_months_uses_current_and_archive_titles_only(self):
        current = date(2026, 8, 1)
        months = available_months(
            [
                "RawData",
                "Archive_2026_06",
                "Archive_2026_07",
                "Backup_RawData_20260801_030354",
                "Archive_bad",
            ],
            current,
        )
        self.assertEqual(
            months,
            (date(2026, 8, 1), date(2026, 7, 1), date(2026, 6, 1)),
        )

    def test_source_sheet_switches_only_for_selected_month(self):
        current = date(2026, 8, 1)
        self.assertEqual(source_sheet_for_month(current, current), "RawData")
        self.assertEqual(
            source_sheet_for_month(date(2026, 7, 1), current),
            "Archive_2026_07",
        )

    def test_month_stats_matches_old_percentage_definition(self):
        rows = [
            parking_row("1/7/2026", "กก1|กรุงเทพมหานคร"),
            parking_row("2/7/2026", "กก1|กรุงเทพมหานคร"),
            parking_row("2/7/2026", "กก1|กรุงเทพมหานคร"),
            parking_row("3/7/2026", "ขข2|นนทบุรี"),
            ["bad date", "อาคาร 4", "คค3", "เชียงใหม่", "คค3", "คค3|เชียงใหม่"],
            [],
        ]
        stats = build_month_stats(date(2026, 7, 1), "Archive_2026_07", rows)
        self.assertEqual(stats.source_rows, 5)
        self.assertEqual(stats.invalid_dates, 1)
        self.assertEqual(stats.period_days, 3)
        self.assertEqual(stats.unique_cars, 2)
        self.assertEqual(len(stats.days_by_key["กก1|กรุงเทพมหานคร"]), 2)
        self.assertEqual(stats.over_80_percent, 0)

    def test_formula_has_no_old_1000_row_limit(self):
        formula = monthly_table_formula()
        self.assertIn("INDIRECT", formula)
        self.assertIn('"Archive_"&TEXT(monthStart,"yyyy_mm")', formula)
        self.assertNotIn("A1000", formula)
        self.assertNotIn("RawData!A", formula)
        self.assertTrue(formula.startswith("=IFERROR(LET("))

    def test_update_requests_clear_month_options_in_one_batch(self):
        requests = build_update_requests(
            99,
            current_month=date(2026, 8, 1),
            selected_month=date(2026, 7, 1),
            months=(date(2026, 8, 1), date(2026, 7, 1), date(2026, 6, 1)),
        )
        month_update = requests[6]["updateCells"]
        self.assertEqual(month_update["start"]["columnIndex"], 16)
        self.assertEqual(len(month_update["rows"]), 1000)
        self.assertEqual(
            month_update["rows"][0]["values"][0]["userEnteredValue"]["numberValue"],
            46235.0,
        )
        self.assertEqual(
            month_update["rows"][1]["values"][0]["userEnteredValue"]["numberValue"],
            46235.0,
        )

    def test_verify_summary_checks_counts_and_percentages(self):
        stats = MonthStats(
            month_start=date(2026, 7, 1),
            source_sheet="Archive_2026_07",
            source_rows=3,
            invalid_dates=0,
            first_date=date(2026, 7, 1),
            last_date=date(2026, 7, 3),
            days_by_key={
                "กก1|กรุงเทพมหานคร": frozenset({date(2026, 7, 1), date(2026, 7, 2)}),
                "ขข2|นนทบุรี": frozenset({date(2026, 7, 3)}),
            },
        )
        values = [["", "", "", 46204, "", 46206, "", 3]] + [[], []]
        values.extend(
            [
                ["กก1|กรุงเทพมหานคร", "กก1", "กรุงเทพมหานคร", 2, 2 / 3],
                ["ขข2|นนทบุรี", "ขข2", "นนทบุรี", 1, 1 / 3],
            ]
        )
        verify_summary_values(values, stats)
        values[3][3] = 1
        with self.assertRaisesRegex(RuntimeError, "percentage verification"):
            verify_summary_values(values, stats)

    def test_load_plan_is_idempotent_and_excludes_backups(self):
        repair = MonthlyRankingRepair(LoadPlanSpreadsheet(), logging.getLogger("test"))
        plan = repair.load_plan(now=datetime(2026, 8, 3, tzinfo=BANGKOK))
        self.assertFalse(plan.needs_update)
        self.assertEqual(plan.months, (date(2026, 8, 1), date(2026, 7, 1)))
        self.assertEqual(plan.stats[date(2026, 7, 1)].source_sheet, "Archive_2026_07")

        old_plan = MonthlyRankingRepair(
            LoadPlanSpreadsheet(old_formula=True), logging.getLogger("test")
        ).load_plan(now=datetime(2026, 8, 3, tzinfo=BANGKOK))
        self.assertTrue(old_plan.needs_update)

    def test_api_error_after_backup_rolls_summary_back(self):
        spreadsheet = FailingWriteSpreadsheet()
        repair = MonthlyRankingRepair(spreadsheet, logging.getLogger("test"))
        current = date(2026, 8, 1)
        stats = MonthStats(
            current, "RawData", 1, 0, current, current, {"key": frozenset({current})}
        )
        plan = MonthlyRankingPlan(
            current_month=current,
            selected_month=current,
            display_mode="ทั้งหมด",
            months=(current,),
            stats={current: stats},
            needs_update=True,
            reasons=("test",),
        )
        with self.assertRaisesRegex(RuntimeError, "simulated Google API failure"):
            repair.execute(plan, now=datetime(2026, 8, 3, tzinfo=BANGKOK))
        self.assertEqual(len(spreadsheet.duplicates), 1)
        self.assertEqual(len(spreadsheet.batch_calls), 2)
        self.assertIn("copyPaste", spreadsheet.batch_calls[1]["requests"][0])


if __name__ == "__main__":
    unittest.main()
