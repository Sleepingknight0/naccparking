from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.google_sheets_service import connect_spreadsheet
from services.monthly_ranking_service import BANGKOK, MonthlyRankingRepair


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Make MonthlyRanking read only the selected RawData/Archive month"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--rollback", metavar="BACKUP_SHEET")
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("monthly-ranking-repair")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    return logger


def confirm(prompt: str) -> bool:
    return input(f"{prompt} [y/N]: ").strip().lower() in {"y", "yes"}


def main() -> int:
    args = parse_args()
    logger = configure_logging()
    try:
        spreadsheet = connect_spreadsheet()
        repair = MonthlyRankingRepair(spreadsheet, logger)
        if args.rollback:
            if not args.yes and not confirm(
                f"Restore MonthlyRanking from {args.rollback}?"
            ):
                logger.info("Rollback cancelled")
                return 0
            repair.rollback(args.rollback)
            logger.info("MonthlyRanking restored from %s", args.rollback)
            return 0

        plan = repair.load_plan()
        logger.info("Timezone: %s", BANGKOK.key)
        logger.info("Current Bangkok month: %s", plan.current_month)
        logger.info("Selected month: %s", plan.selected_month)
        for month in plan.months:
            stats = plan.stats[month]
            logger.info(
                "%s: %s rows, %s unique cars, %s-day period, %s over 80%%, %s invalid dates",
                stats.source_sheet,
                f"{stats.source_rows:,}",
                f"{stats.unique_cars:,}",
                stats.period_days,
                stats.over_80_percent,
                stats.invalid_dates,
            )
        logger.info("Update required: %s", "yes" if plan.needs_update else "no")
        for reason in plan.reasons:
            logger.info("Reason: %s", reason)

        if args.dry_run:
            logger.info("Dry run completed. No data was modified.")
            return 0
        if not plan.needs_update:
            logger.info("MonthlyRanking is already current. No data was modified.")
            return 0
        if not args.yes and not confirm("Back up and repair MonthlyRanking?"):
            logger.info("Repair cancelled")
            return 0

        result = repair.execute(plan)
        logger.info(
            "Verification passed for: %s", ", ".join(map(str, result.verified_months))
        )
        logger.info("Backup: %s", result.backup_name)
        logger.info("MonthlyRanking updated successfully")
        return 0
    except Exception:
        logger.exception("MonthlyRanking operation failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
