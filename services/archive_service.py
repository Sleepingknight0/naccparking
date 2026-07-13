from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

from services.google_sheets_service import GoogleSheetsService


BANGKOK = ZoneInfo("Asia/Bangkok")
SOURCE_SHEET = "RawData"
DATE_COLUMN = 0
IDENTITY_COLUMNS = (0, 1, 2, 3)
SUPPORTED_DATE_FORMATS = (
    "%d/%m/%Y",
    "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
)


@dataclass(frozen=True)
class InvalidDateRow:
    sheet_row: int
    value: object


@dataclass
class ArchivePlan:
    header: list[object]
    original_body: list[list[object]]
    source_rows: list[list[object]]
    retained_rows: list[list[object]]
    archive_rows: dict[str, list[list[object]]]
    invalid_dates: list[InvalidDateRow]
    blank_rows: list[int]
    duplicate_rows: int
    archive_duplicate_rows: int
    source_span: int
    cutoff: date

    @property
    def source_total(self) -> int:
        return len(self.source_rows)

    @property
    def archive_total(self) -> int:
        return sum(len(rows) for rows in self.archive_rows.values())


@dataclass(frozen=True)
class MigrationResult:
    backup_name: str
    appended_rows: int
    already_archived_rows: int
    retained_rows: int


def bangkok_now() -> datetime:
    return datetime.now(BANGKOK)


def first_day_of_current_month(now: datetime | None = None) -> date:
    current = (now or bangkok_now()).astimezone(BANGKOK)
    return date(current.year, current.month, 1)


def archive_sheet_name(value: date | datetime) -> str:
    return f"Archive_{value.year:04d}_{value.month:02d}"


def parse_parking_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        parsed = datetime(1899, 12, 30) + timedelta(days=float(value))
    else:
        text = str(value).strip() if value is not None else ""
        if not text:
            return None
        parsed = None
        for date_format in SUPPORTED_DATE_FORMATS:
            try:
                parsed = datetime.strptime(text, date_format)
                break
            except ValueError:
                continue
        if parsed is None:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=BANGKOK)
    return parsed.astimezone(BANGKOK)


def build_archive_plan(
    values: list[list[object]],
    *,
    now: datetime | None = None,
) -> ArchivePlan:
    cutoff = first_day_of_current_month(now)
    if not values:
        return ArchivePlan([], [], [], [], {}, [], [], 0, 0, 0, cutoff)

    width = max(4, max(len(row) for row in values))
    header = _pad(values[0], width)
    body = [_pad(row, width) for row in values[1:]]
    logical_indexes = [index for index, row in enumerate(body) if _has_source_data(row)]
    source_span = logical_indexes[-1] + 1 if logical_indexes else 0
    original_body = body[:source_span]

    source_rows: list[list[object]] = []
    retained_rows: list[list[object]] = []
    grouped: dict[str, list[list[object]]] = defaultdict(list)
    invalid_dates: list[InvalidDateRow] = []
    blank_rows: list[int] = []
    all_keys: Counter[tuple[str, ...]] = Counter()
    archive_keys: Counter[tuple[str, ...]] = Counter()

    for index, row in enumerate(original_body):
        sheet_row = index + 2
        if not _has_source_data(row):
            blank_rows.append(sheet_row)
            continue
        source_rows.append(row)
        parsed = parse_parking_datetime(row[DATE_COLUMN])
        if parsed is None:
            invalid_dates.append(InvalidDateRow(sheet_row, row[DATE_COLUMN]))
            retained_rows.append(row)
            continue

        key = row_identity(row, parsed)
        all_keys[key] += 1
        if parsed.date() < cutoff:
            grouped[archive_sheet_name(parsed)].append(row)
            archive_keys[key] += 1
        else:
            retained_rows.append(row)

    return ArchivePlan(
        header=header,
        original_body=original_body,
        source_rows=source_rows,
        retained_rows=retained_rows,
        archive_rows=dict(sorted(grouped.items())),
        invalid_dates=invalid_dates,
        blank_rows=blank_rows,
        duplicate_rows=sum(count - 1 for count in all_keys.values() if count > 1),
        archive_duplicate_rows=sum(
            count - 1 for count in archive_keys.values() if count > 1
        ),
        source_span=source_span,
        cutoff=cutoff,
    )


def row_identity(
    row: list[object],
    parsed: datetime | None = None,
) -> tuple[str, ...]:
    parsed = parsed or parse_parking_datetime(row[DATE_COLUMN])
    date_value = parsed.date().isoformat() if parsed else str(row[DATE_COLUMN]).strip()
    return (date_value,) + tuple(
        str(row[index]).strip().upper() if index < len(row) else ""
        for index in IDENTITY_COLUMNS[1:]
    )


def rows_to_append(
    source_rows: Iterable[list[object]],
    existing_rows: Iterable[list[object]],
) -> list[list[object]]:
    """Multiset comparison preserves pre-existing duplicates but makes retries idempotent."""
    existing_counts = Counter(
        row_identity(row)
        for row in existing_rows
        if _has_source_data(row) and parse_parking_datetime(row[DATE_COLUMN]) is not None
    )
    source_seen: Counter[tuple[str, ...]] = Counter()
    result = []
    for row in source_rows:
        key = row_identity(row)
        source_seen[key] += 1
        if source_seen[key] > existing_counts[key]:
            result.append(row)
    return result


class ArchiveMigration:
    def __init__(self, sheets: GoogleSheetsService, logger: logging.Logger):
        self.sheets = sheets
        self.logger = logger

    def load_plan(self, *, now: datetime | None = None) -> ArchivePlan:
        self.logger.info("Connected to spreadsheet")
        self.logger.info("Source sheet: %s", SOURCE_SHEET)
        values = self.sheets.read_worksheets([SOURCE_SHEET])[SOURCE_SHEET]
        return build_archive_plan(values, now=now)

    def execute(self, plan: ArchivePlan, *, now: datetime | None = None) -> MigrationResult:
        now = (now or bangkok_now()).astimezone(BANGKOK)
        backup_name = f"Backup_RawData_{now:%Y%m%d_%H%M%S}"
        self.sheets.create_backup(SOURCE_SHEET, backup_name)
        self.logger.info("Backup created: %s", backup_name)

        archive_names = list(plan.archive_rows)
        existing_names = self.sheets.worksheet_names()
        existing_archive_names = [name for name in archive_names if name in existing_names]
        existing_values = self.sheets.read_worksheets(existing_archive_names)
        for name in archive_names:
            if name in existing_values:
                _validate_archive_header(name, plan.header, existing_values[name])

        sheet_ids = self.sheets.ensure_worksheets(
            archive_names,
            rows=max((len(rows) + 1 for rows in plan.archive_rows.values()), default=2),
            cols=max(len(plan.header), 4),
        )
        del sheet_ids  # IDs are resolved inside the formatting batch.

        writes: list[tuple[str, int, list[list[object]]]] = []
        format_destinations: dict[str, tuple[int, int]] = {}
        expected_archive_counts: dict[str, Counter[tuple[str, ...]]] = {}
        appended_total = 0
        already_archived = 0
        for name, source_rows in plan.archive_rows.items():
            archive_values = existing_values.get(name, [])
            archive_body = archive_values[1:] if archive_values else []
            append = rows_to_append(source_rows, archive_body)
            already_archived += len(source_rows) - len(append)
            start_row = _last_logical_row(archive_values) + 1 if archive_values else 2
            if not archive_values:
                writes.append((name, 1, [plan.header]))
            if append:
                writes.append((name, start_row, append))
                format_destinations[name] = (start_row, len(append))
            elif not archive_values:
                format_destinations[name] = (2, 0)
            appended_total += len(append)
            expected_archive_counts[name] = Counter(
                row_identity(row) for row in _logical_rows(archive_body)
            ) + Counter(row_identity(row) for row in append)
            self.logger.info("%s: %s rows to append", name, len(append))

        self.sheets.batch_write_values(writes)
        self.sheets.copy_source_formats(
            SOURCE_SHEET,
            format_destinations,
            column_count=max(len(plan.header), 4),
        )

        verified_values = self.sheets.read_worksheets(archive_names)
        _verify_archives(plan, verified_values, expected_archive_counts)
        self.logger.info("Archive verification passed")

        accounted = appended_total + already_archived
        if plan.source_total != len(plan.retained_rows) + accounted:
            raise RuntimeError(
                "Count verification failed before RawData update: "
                "source != retained + archived/accounted"
            )

        source_updated = False
        try:
            self.sheets.replace_source_columns(
                SOURCE_SHEET,
                [row[:4] for row in plan.retained_rows],
                clear_through_row_count=plan.source_span,
            )
            source_updated = True
            current_values = self.sheets.read_worksheets([SOURCE_SHEET])[SOURCE_SHEET]
            actual_rows = _logical_rows(current_values[1:] if current_values else [])
            expected_rows = [row[:4] for row in plan.retained_rows]
            if [row[:4] for row in actual_rows] != expected_rows:
                raise RuntimeError("RawData verification failed after update")
        except Exception:
            if source_updated:
                self.logger.error("RawData update verification failed; restoring source snapshot")
                self.sheets.replace_source_columns(
                    SOURCE_SHEET,
                    [row[:4] for row in plan.original_body],
                    clear_through_row_count=max(plan.source_span, len(plan.retained_rows)),
                )
            raise

        self.logger.info("Verification passed")
        self.logger.info("RawData updated successfully")
        return MigrationResult(
            backup_name=backup_name,
            appended_rows=appended_total,
            already_archived_rows=already_archived,
            retained_rows=len(plan.retained_rows),
        )

    def rollback(self, backup_name: str) -> int:
        names = self.sheets.worksheet_names()
        if backup_name not in names:
            raise RuntimeError(f"Backup sheet not found: {backup_name}")
        values = self.sheets.read_worksheets([backup_name])[backup_name]
        plan = build_archive_plan(values)
        self.sheets.replace_source_columns(
            SOURCE_SHEET,
            [row[:4] for row in plan.original_body],
            clear_through_row_count=plan.source_span,
        )
        self.logger.info("RawData restored from %s", backup_name)
        return len(plan.source_rows)


def _validate_archive_header(
    name: str,
    expected_header: list[object],
    values: list[list[object]],
) -> None:
    if not values:
        return
    actual = _pad(values[0], len(expected_header))
    if actual != expected_header:
        raise RuntimeError(f"Header mismatch in {name}; refusing to append")


def _verify_archives(
    plan: ArchivePlan,
    archive_values: dict[str, list[list[object]]],
    expected_counts: dict[str, Counter[tuple[str, ...]]],
) -> None:
    for name, source_rows in plan.archive_rows.items():
        values = archive_values.get(name, [])
        _validate_archive_header(name, plan.header, values)
        actual_counts = Counter(row_identity(row) for row in _logical_rows(values[1:]))
        source_required = Counter(row_identity(row) for row in source_rows)
        missing = source_required - actual_counts
        if missing:
            raise RuntimeError(
                f"Archive verification failed for {name}: {sum(missing.values())} rows missing"
            )
        if actual_counts != expected_counts[name]:
            raise RuntimeError(
                f"Archive verification failed for {name}: unexpected row count change"
            )


def _logical_rows(rows: Iterable[list[object]]) -> list[list[object]]:
    return [list(row) for row in rows if _has_source_data(row)]


def _last_logical_row(values: list[list[object]]) -> int:
    last = 1
    for index, row in enumerate(values[1:], start=2):
        if _has_source_data(row):
            last = index
    return last


def _has_source_data(row: list[object]) -> bool:
    return any(
        index < len(row) and row[index] not in (None, "")
        for index in IDENTITY_COLUMNS
    )


def _pad(row: list[object], width: int) -> list[object]:
    return list(row) + [""] * (width - len(row))
