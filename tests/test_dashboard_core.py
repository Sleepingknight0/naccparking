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
from dashboard.metrics import build_week_options, compute_kpis, filter_dataframe


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


if __name__ == "__main__":
    unittest.main()
