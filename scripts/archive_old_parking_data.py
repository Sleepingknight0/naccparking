from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.archive_service import ArchiveMigration, ArchivePlan, bangkok_now
from services.google_sheets_service import GoogleSheetsService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive old RawData rows by Bangkok month")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Read and report only")
    mode.add_argument("--execute", action="store_true", help="Back up and migrate")
    mode.add_argument("--rollback", metavar="BACKUP_SHEET", help="Restore RawData A:D")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation")
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="Skip safely unless today is day 1 in Asia/Bangkok",
    )
    return parser.parse_args()


def configure_logging() -> logging.Logger:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = bangkok_now().strftime("%Y%m%d_%H%M%S")
    logger = logging.getLogger("parking_archive")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    logger.handlers.clear()
    for handler in (
        logging.StreamHandler(),
        logging.FileHandler(log_dir / f"archive_{timestamp}.log", encoding="utf-8"),
    ):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def print_summary(plan: ArchivePlan, logger: logging.Logger) -> None:
    logger.info("Found %s rows", f"{plan.source_total:,}")
    logger.info("Current month/retained: %s rows", f"{len(plan.retained_rows):,}")
    logger.info("Archiving %s rows", f"{plan.archive_total:,}")
    for name, rows in plan.archive_rows.items():
        logger.info("%s: %s rows", name, f"{len(rows):,}")
    logger.info("Archive sheets to create/use: %s", ", ".join(plan.archive_rows) or "none")
    logger.info("Invalid date rows: %s", len(plan.invalid_dates))
    for invalid in plan.invalid_dates:
        logger.warning("Invalid date at RawData row %s: %r", invalid.sheet_row, invalid.value)
    logger.info("Blank rows between data: %s", len(plan.blank_rows))
    logger.info("Duplicate rows: %s", plan.duplicate_rows)
    logger.info("Duplicate rows to archive: %s", plan.archive_duplicate_rows)


def confirm(prompt: str) -> bool:
    return input(f"{prompt} [y/N]: ").strip().lower() in {"y", "yes"}


def main() -> int:
    args = parse_args()
    logger = configure_logging()
    now = bangkok_now()
    if args.scheduled and now.day != 1:
        logger.info("Scheduled run skipped: Bangkok date is %s", now.date())
        return 0

    try:
        migration = ArchiveMigration(GoogleSheetsService.connect(), logger)
        if args.rollback:
            if not args.yes and not confirm(f"Restore RawData from {args.rollback}?"):
                logger.info("Rollback cancelled")
                return 0
            count = migration.rollback(args.rollback)
            logger.info("Rollback completed: %s logical rows restored", count)
            return 0

        plan = migration.load_plan(now=now)
        print_summary(plan, logger)
        if args.dry_run:
            logger.info("Dry run completed. No data was modified.")
            return 0
        if not plan.archive_total:
            logger.info("No old rows to archive. No data was modified.")
            return 0
        if not args.yes and not confirm("Create backup and execute migration?"):
            logger.info("Migration cancelled")
            return 0

        result = migration.execute(plan, now=now)
        logger.info("Backup: %s", result.backup_name)
        logger.info("Rows added to Archive: %s", result.appended_rows)
        logger.info("Rows already safely archived: %s", result.already_archived_rows)
        logger.info("Rows remaining in RawData: %s", result.retained_rows)
        return 0
    except Exception as exc:
        logger.exception("Archive operation failed at current step: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
