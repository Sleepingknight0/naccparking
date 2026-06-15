import unittest
from datetime import date

import pandas as pd

from dashboard.data_service import (
    BUILDING_COL,
    DATE_COL,
    NORMALIZED_PLATE_COL,
    OVERNIGHT_COL,
    PLATE_COL,
    PROVINCE_COL,
    canonicalize_columns,
    normalize_plate,
    prepare_dashboard_dataframe,
)
from dashboard.display import prepare_display_dataframe
from dashboard.home_summary import get_today_building_counts, get_today_records
from dashboard.metrics import build_week_options, compute_kpis, filter_dataframe, summarize_by_building


class DashboardDataServiceTests(unittest.TestCase):
    def test_normalize_plate_removes_spacing_and_dash_variants(self):
        self.assertEqual(normalize_plate(" กก - 1234 "), "กก1234")
        self.assertEqual(normalize_plate("ab--  99"), "AB99")
        self.assertEqual(normalize_plate(None), "")

    def test_canonicalize_columns_uses_aliases_without_losing_original_data(self):
        raw = pd.DataFrame(
            {
                "Date": ["2026-06-12"],
                "building": ["อาคาร 4"],
                "plate": ["กก 1234"],
                "province": ["กรุงเทพมหานคร"],
            }
        )

        canonical = canonicalize_columns(raw)

        self.assertEqual(canonical.loc[0, DATE_COL], "2026-06-12")
        self.assertEqual(canonical.loc[0, BUILDING_COL], "อาคาร 4")
        self.assertEqual(canonical.loc[0, PLATE_COL], "กก 1234")
        self.assertEqual(canonical.loc[0, PROVINCE_COL], "กรุงเทพมหานคร")

    def test_prepare_dataframe_adds_overnight_derived_columns(self):
        raw = pd.DataFrame(
            {
                DATE_COL: ["2026-06-12", "2026-06-13", "2026-06-16"],
                BUILDING_COL: ["อาคาร 4", "อาคาร 4", "อาคาร 8"],
                PLATE_COL: ["กก 1234", "กก-1234", "ขข 8888"],
                PROVINCE_COL: ["กรุงเทพมหานคร", "กรุงเทพมหานคร", "เชียงใหม่"],
            }
        )

        prepared = prepare_dashboard_dataframe(raw)
        first_vehicle = prepared[prepared[NORMALIZED_PLATE_COL] == "กก1234"]

        self.assertEqual(len(prepared), 3)
        self.assertTrue(first_vehicle[OVERNIGHT_COL].all())
        self.assertIn("พบต่อเนื่อง", first_vehicle["overnight_reason"].iloc[0])
        self.assertEqual(first_vehicle["gap_days"].dropna().iloc[0], 1)


class DashboardMetricsTests(unittest.TestCase):
    def setUp(self):
        raw = pd.DataFrame(
            {
                DATE_COL: ["2026-06-12", "2026-06-13", "2026-06-13"],
                BUILDING_COL: ["อาคาร 4", "อาคาร 4", "อาคาร 8"],
                PLATE_COL: ["กก 1234", "กก 1234", "ขข 8888"],
                PROVINCE_COL: ["กรุงเทพมหานคร", "กรุงเทพมหานคร", "เชียงใหม่"],
            }
        )
        self.df = prepare_dashboard_dataframe(raw)

    def test_compute_kpis_counts_records_unique_vehicles_and_overnight(self):
        kpis = compute_kpis(self.df)

        self.assertEqual(kpis["total_records"], 3)
        self.assertEqual(kpis["unique_vehicles"], 2)
        self.assertEqual(kpis["building_count"], 2)
        self.assertEqual(kpis["overnight_count"], 2)
        self.assertEqual(kpis["busiest_day"], date(2026, 6, 13))
        self.assertEqual(kpis["top_building"], "อาคาร 4")

    def test_filter_dataframe_filters_building_province_month_and_date_range(self):
        filtered = filter_dataframe(
            self.df,
            buildings=["อาคาร 4"],
            provinces=["กรุงเทพมหานคร"],
            year=2026,
            month=6,
            date_range=(date(2026, 6, 13), date(2026, 6, 13)),
        )

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0][BUILDING_COL], "อาคาร 4")
        self.assertEqual(filtered.iloc[0][DATE_COL], date(2026, 6, 13))

    def test_build_week_options_returns_weeks_that_intersect_selected_month(self):
        weeks = build_week_options(2026, 6)

        self.assertEqual(weeks[0]["start"], date(2026, 6, 1))
        self.assertEqual(weeks[-1]["end"], date(2026, 6, 30))
        self.assertTrue(all(week["start"].month == 6 or week["end"].month == 6 for week in weeks))

    def test_summarize_by_building_returns_stable_schema_when_columns_are_missing(self):
        partial = pd.DataFrame({"ทะเบียนรถ": ["กก 1234", "ขข 8888"]})

        summary = summarize_by_building(partial)

        self.assertEqual(
            summary.columns.tolist(),
            ["อาคาร", "จำนวนรายการ", "จำนวนทะเบียนไม่ซ้ำ", "จำนวนรถค้างคืน", "คิดเป็นสัดส่วน"],
        )
        self.assertEqual(summary.loc[0, "อาคาร"], "ไม่ระบุอาคาร")
        self.assertEqual(summary.loc[0, "จำนวนรายการ"], 2)
        self.assertEqual(summary.loc[0, "จำนวนรถค้างคืน"], 0)
        self.assertEqual(summary.loc[0, "คิดเป็นสัดส่วน"], "100.0%")

    def test_summarize_by_building_empty_frame_keeps_stable_schema(self):
        summary = summarize_by_building(pd.DataFrame())

        self.assertEqual(
            summary.columns.tolist(),
            ["อาคาร", "จำนวนรายการ", "จำนวนทะเบียนไม่ซ้ำ", "จำนวนรถค้างคืน", "คิดเป็นสัดส่วน"],
        )
        self.assertTrue(summary.empty)


class DashboardDisplayTests(unittest.TestCase):
    def test_prepare_display_dataframe_uses_thai_headers_and_hides_system_columns_by_default(self):
        raw = pd.DataFrame(
            {
                DATE_COL: ["2026-06-12", "2026-06-13"],
                BUILDING_COL: ["อาคาร 4", "อาคาร 4"],
                PLATE_COL: ["กก 1234", "กก 1234"],
                PROVINCE_COL: ["กรุงเทพมหานคร", "กรุงเทพมหานคร"],
            }
        )
        prepared = prepare_dashboard_dataframe(raw)

        display_df = prepare_display_dataframe(prepared, include_system_columns=False)

        self.assertIn("วันที่", display_df.columns)
        self.assertIn("ทะเบียนรถ", display_df.columns)
        self.assertIn("สถานะค้างคืน", display_df.columns)
        self.assertIn("เหตุผลค้างคืน", display_df.columns)
        self.assertNotIn("normalized_plate", display_df.columns)
        self.assertNotIn("record_datetime", display_df.columns)
        self.assertNotIn("year_month", display_df.columns)

    def test_prepare_display_dataframe_appends_thai_system_columns_when_enabled(self):
        raw = pd.DataFrame(
            {
                DATE_COL: ["2026-06-12"],
                BUILDING_COL: ["อาคาร 4"],
                PLATE_COL: ["กก 1234"],
                PROVINCE_COL: ["กรุงเทพมหานคร"],
            }
        )
        prepared = prepare_dashboard_dataframe(raw)

        display_df = prepare_display_dataframe(prepared, include_system_columns=True)

        self.assertIn("ทะเบียนรถมาตรฐาน", display_df.columns)
        self.assertIn("รหัสรถ", display_df.columns)
        self.assertIn("วันที่/เวลาบันทึก", display_df.columns)


class HomeSummaryTests(unittest.TestCase):
    def test_get_today_records_parses_iso_and_thai_slash_dates(self):
        raw = pd.DataFrame(
            {
                "วันที่ตรวจพบ": ["2026-06-16", "16/6/2026", "2026-06-15"],
                "อาคาร": ["อาคาร 1", "อาคาร 2", "อาคาร 1"],
                "ทะเบียนรถ": ["กก 1", "กก 2", "กก 3"],
            }
        )

        today_df = get_today_records(raw, today=date(2026, 6, 16))

        self.assertEqual(len(today_df), 2)
        self.assertEqual(today_df["อาคาร"].tolist(), ["อาคาร 1", "อาคาร 2"])

    def test_get_today_building_counts_uses_first_five_configured_buildings_and_total_all(self):
        raw = pd.DataFrame(
            {
                "วันที่ตรวจพบ": ["2026-06-16"] * 7,
                "อาคาร": ["อาคาร 1", "อาคาร 1", "อาคาร 2", "อาคาร 6", "อาคาร 6", "อาคาร 6", "อื่น"],
            }
        )
        buildings = ["อาคาร 1", "อาคาร 2", "อาคาร 3", "อาคาร 4", "อาคาร 5", "อาคาร 6"]

        cards = get_today_building_counts(raw, buildings, today=date(2026, 6, 16))

        self.assertEqual([card["label"] for card in cards], ["อาคาร 1", "อาคาร 2", "อาคาร 3", "อาคาร 4", "อาคาร 5", "รวมทุกอาคาร"])
        self.assertEqual([card["count"] for card in cards], [2, 1, 0, 0, 0, 7])

    def test_get_today_building_counts_fills_missing_building_slots(self):
        raw = pd.DataFrame({"วันที่ตรวจพบ": ["2026-06-16"], "อาคาร": ["อาคาร 1"]})

        cards = get_today_building_counts(raw, ["อาคาร 1"], today=date(2026, 6, 16))

        self.assertEqual(cards[0]["label"], "อาคาร 1")
        self.assertEqual(cards[1]["label"], "ยังไม่มีอาคาร")
        self.assertEqual(cards[5]["label"], "รวมทุกอาคาร")
        self.assertEqual(cards[5]["count"], 1)


if __name__ == "__main__":
    unittest.main()
