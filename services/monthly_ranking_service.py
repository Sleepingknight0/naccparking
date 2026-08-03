from __future__ import annotations

import re
import time
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from services.archive_service import parse_parking_datetime

BANGKOK = ZoneInfo("Asia/Bangkok")
SUMMARY_SHEET = "MonthlyRanking"
RAW_SHEET = "RawData"
ARCHIVE_PATTERN = re.compile(r"^Archive_(\d{4})_(\d{2})$")
MONTH_OPTION_COLUMN = 16  # Q, zero-based
SUMMARY_ROWS = 1000
SUMMARY_COLUMNS = 17


@dataclass(frozen=True)
class MonthStats:
    month_start: date
    source_sheet: str
    source_rows: int
    invalid_dates: int
    first_date: date | None
    last_date: date | None
    days_by_key: dict[str, frozenset[date]]

    @property
    def period_days(self) -> int:
        if self.first_date is None or self.last_date is None:
            return 0
        return (self.last_date - self.first_date).days + 1

    @property
    def unique_cars(self) -> int:
        return len(self.days_by_key)

    @property
    def over_80_percent(self) -> int:
        if not self.period_days:
            return 0
        return sum(
            len(days) / self.period_days > 0.8 for days in self.days_by_key.values()
        )


@dataclass(frozen=True)
class MonthlyRankingPlan:
    current_month: date
    selected_month: date
    display_mode: str
    months: tuple[date, ...]
    stats: dict[date, MonthStats]
    needs_update: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class MonthlyRankingResult:
    backup_name: str | None
    verified_months: tuple[date, ...]
    changed: bool


def bangkok_month_start(now: datetime | None = None) -> date:
    current = (now or datetime.now(BANGKOK)).astimezone(BANGKOK)
    return date(current.year, current.month, 1)


def archive_month_from_title(title: str) -> date | None:
    match = ARCHIVE_PATTERN.fullmatch(title)
    if not match:
        return None
    year, month = (int(value) for value in match.groups())
    try:
        return date(year, month, 1)
    except ValueError:
        return None


def source_sheet_for_month(month_start: date, current_month: date) -> str:
    if month_start == current_month:
        return RAW_SHEET
    return f"Archive_{month_start.year:04d}_{month_start.month:02d}"


def available_months(titles: Iterable[str], current_month: date) -> tuple[date, ...]:
    months = {current_month}
    months.update(
        month
        for title in titles
        if (month := archive_month_from_title(title)) is not None
    )
    return tuple(sorted(months, reverse=True))


def build_month_stats(
    month_start: date,
    source_sheet: str,
    rows: Iterable[list[object]],
) -> MonthStats:
    days_by_key: dict[str, set[date]] = defaultdict(set)
    dates: list[date] = []
    invalid_dates = 0
    source_rows = 0

    for original in rows:
        row = list(original) + [""] * max(0, 6 - len(original))
        if not any(value not in (None, "") for value in row[:4]):
            continue
        source_rows += 1
        parsed = parse_parking_datetime(row[0])
        if parsed is None:
            invalid_dates += 1
            continue
        parsed_date = parsed.date()
        if (
            parsed_date.year != month_start.year
            or parsed_date.month != month_start.month
        ):
            continue
        dates.append(parsed_date)
        key = str(row[5]).strip()
        if key:
            days_by_key[key].add(parsed_date)

    frozen_days = {key: frozenset(value) for key, value in days_by_key.items()}
    return MonthStats(
        month_start=month_start,
        source_sheet=source_sheet,
        source_rows=source_rows,
        invalid_dates=invalid_dates,
        first_date=min(dates) if dates else None,
        last_date=max(dates) if dates else None,
        days_by_key=frozen_days,
    )


def first_or_last_date_formula(function_name: str) -> str:
    if function_name not in {"MIN", "MAX"}:
        raise ValueError("function_name must be MIN or MAX")
    return (
        "=IFERROR(LET(monthStart,DATE(YEAR($B$1),MONTH($B$1),1),"
        'sourceName,IF(monthStart=$Q$1,"RawData","Archive_"&TEXT(monthStart,"yyyy_mm")),'
        'rawDates,INDIRECT("\'"&sourceName&"\'!A2:A"),'
        'dates,FILTER(ARRAYFORMULA(IFERROR(DATEVALUE(rawDates),rawDates)),rawDates<>""),'
        f'{function_name}(FILTER(dates,dates>=monthStart,dates<=EOMONTH(monthStart,0)))),"")'
    )


def monthly_table_formula() -> str:
    return (
        "=IFERROR(LET(monthStart,DATE(YEAR($B$1),MONTH($B$1),1),"
        "monthEnd,EOMONTH(monthStart,0),"
        'sourceName,IF(monthStart=$Q$1,"RawData","Archive_"&TEXT(monthStart,"yyyy_mm")),'
        'sourceA,INDIRECT("\'"&sourceName&"\'!A2:A"),'
        'sourceB,INDIRECT("\'"&sourceName&"\'!B2:B"),'
        'sourceC,INDIRECT("\'"&sourceName&"\'!C2:C"),'
        'sourceD,INDIRECT("\'"&sourceName&"\'!D2:D"),'
        'sourceF,INDIRECT("\'"&sourceName&"\'!F2:F"),'
        "dates,ARRAYFORMULA(IFERROR(DATEVALUE(sourceA),sourceA)),"
        'monthDates,FILTER(dates,dates>=monthStart,dates<=monthEnd,sourceA<>""),'
        "firstDate,MIN(monthDates),lastDate,MAX(monthDates),"
        "periodDays,lastDate-firstDate+1,"
        "source,FILTER({sourceF,sourceC,sourceD,dates},dates>=firstDate,"
        'dates<=lastDate,sourceF<>""),'
        "ranked,QUERY(UNIQUE(source),"
        '"select Col1, max(Col2), max(Col3), count(Col4), min(Col4), max(Col4) '
        "group by Col1 order by count(Col4) desc label Col1 '', max(Col2) '', "
        "max(Col3) '', count(Col4) '', min(Col4) '', max(Col4) ''\",0),"
        "keys,INDEX(ranked,,1),"
        "dayText,LAMBDA(dayDates,IFERROR(LET("
        'dayList,ARRAYFORMULA(TEXT(SORT(UNIQUE(dayDates)),"d")),'
        "dayPositions,SEQUENCE(ROWS(dayList)),"
        "TEXTJOIN(CHAR(10),TRUE,MAP(SEQUENCE(ROUNDUP(ROWS(dayList)/5,0)),LAMBDA(g,"
        'TEXTJOIN(", ",TRUE,FILTER(dayList,dayPositions>(g-1)*5,dayPositions<=g*5)))))),"")),'
        "allDays,MAP(keys,LAMBDA(k,dayText(FILTER(dates,sourceF=k,"
        "dates>=firstDate,dates<=lastDate)))),"
        "buildingDays,LAMBDA(buildingName,MAP(keys,LAMBDA(k,dayText(FILTER(dates,"
        "sourceF=k,ARRAYFORMULA(TRIM(TO_TEXT(sourceB)))=TRIM(buildingName),"
        "dates>=firstDate,dates<=lastDate))))),"
        "building1,buildingDays($K$3),building2,buildingDays($L$3),"
        "building3,buildingDays($M$3),building4,buildingDays($N$3),"
        "building5,buildingDays($O$3),"
        "table,{keys,INDEX(ranked,,2),INDEX(ranked,,3),INDEX(ranked,,4),"
        "ARRAYFORMULA(INDEX(ranked,,4)/periodDays),"
        'ARRAYFORMULA(IF(INDEX(ranked,,4)/periodDays>0.8,"เกิน 80%","")),'
        'ARRAYFORMULA(TEXT(INDEX(ranked,,5),"d/m/yyyy")),'
        'ARRAYFORMULA(TEXT(INDEX(ranked,,6),"d/m/yyyy")),allDays,'
        'ARRAYFORMULA(IF(INDEX(ranked,,6)=lastDate,"ยังเจอ","ไม่เจอ")),'
        "building1,building2,building3,building4,building5},"
        'FILTER(table,IF($B$2="เฉพาะเกิน 80%",INDEX(table,,5)>0.8,'
        'INDEX(table,,1)<>""))),"")'
    )


def build_update_requests(
    sheet_id: int,
    *,
    current_month: date,
    selected_month: date,
    months: tuple[date, ...],
) -> list[dict[str, object]]:
    option_rows = [current_month, *months]
    q_rows = [
        {"values": [{"userEnteredValue": {"numberValue": _date_serial(value)}}]}
        for value in option_rows
    ]
    q_rows.extend({"values": [{}]} for _ in range(SUMMARY_ROWS - len(option_rows)))
    return [
        _single_cell_request(sheet_id, 0, 1, number=_date_serial(selected_month)),
        _single_cell_request(sheet_id, 0, 3, formula=first_or_last_date_formula("MIN")),
        _single_cell_request(sheet_id, 0, 5, formula=first_or_last_date_formula("MAX")),
        _single_cell_request(
            sheet_id,
            0,
            7,
            formula='=IF(OR(D1="",F1=""),"",F1-D1+1)',
        ),
        _single_cell_request(
            sheet_id,
            0,
            10,
            formula='=IF(H1="","",ROUNDUP(H1*80%,0))',
        ),
        _single_cell_request(sheet_id, 3, 0, formula=monthly_table_formula()),
        {
            "updateCells": {
                "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 16},
                "rows": q_rows,
                "fields": "userEnteredValue",
            }
        },
        _date_format_request(sheet_id, 0, 1, 1, 2),
        _date_format_request(sheet_id, 0, 3, 1, 4),
        _date_format_request(sheet_id, 0, 5, 1, 6),
        _date_format_request(sheet_id, 0, 16, SUMMARY_ROWS, 17),
        {
            "setDataValidation": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 1,
                    "endColumnIndex": 2,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_RANGE",
                        "values": [
                            {"userEnteredValue": ("='MonthlyRanking'!$Q$2:$Q$1000")}
                        ],
                    },
                    "strict": True,
                    "showCustomUi": True,
                },
            }
        },
    ]


def verify_summary_values(values: list[list[object]], expected: MonthStats) -> None:
    if not expected.period_days:
        raise RuntimeError(f"No valid rows found in {expected.source_sheet}")

    def cell(row: int, column: int) -> object:
        if row >= len(values) or column >= len(values[row]):
            return ""
        return values[row][column]

    actual_first = _serial_date(cell(0, 3))
    actual_last = _serial_date(cell(0, 5))
    if actual_first != expected.first_date or actual_last != expected.last_date:
        raise RuntimeError(
            f"Monthly date verification failed for {expected.source_sheet}: "
            f"expected {expected.first_date}..{expected.last_date}, "
            f"got {actual_first}..{actual_last}"
        )
    if int(cell(0, 7)) != expected.period_days:
        raise RuntimeError(
            f"Monthly period verification failed for {expected.source_sheet}"
        )

    actual: dict[str, tuple[int, float]] = {}
    for row in values[3:]:
        key = str(row[0]).strip() if row else ""
        if not key:
            continue
        count = int(row[3]) if len(row) > 3 and row[3] not in (None, "") else 0
        percent = float(row[4]) if len(row) > 4 and row[4] not in (None, "") else 0.0
        actual[key] = (count, percent)

    expected_keys = set(expected.days_by_key)
    if set(actual) != expected_keys:
        raise RuntimeError(
            f"Monthly car verification failed for {expected.source_sheet}: "
            f"expected {len(expected_keys)}, got {len(actual)}"
        )
    for key, days in expected.days_by_key.items():
        expected_count = len(days)
        count, percent = actual[key]
        if (
            count != expected_count
            or abs(percent - expected_count / expected.period_days) > 1e-9
        ):
            raise RuntimeError(
                f"Monthly percentage verification failed in {expected.source_sheet}"
            )


class MonthlyRankingRepair:
    def __init__(self, spreadsheet, logger):
        self.spreadsheet = spreadsheet
        self.logger = logger

    def load_plan(self, *, now: datetime | None = None) -> MonthlyRankingPlan:
        current_month = bangkok_month_start(now)
        worksheets = self.spreadsheet.worksheets()
        titles = [worksheet.title for worksheet in worksheets]
        if SUMMARY_SHEET not in titles:
            raise RuntimeError(f"Missing sheet: {SUMMARY_SHEET}")
        if RAW_SHEET not in titles:
            raise RuntimeError(f"Missing sheet: {RAW_SHEET}")

        months = available_months(titles, current_month)
        source_names = [
            source_sheet_for_month(month, current_month) for month in months
        ]
        response = self.spreadsheet.values_batch_get(
            [f"'{_escape(name)}'!A2:F" for name in source_names],
            params={
                "valueRenderOption": "FORMATTED_VALUE",
                "dateTimeRenderOption": "FORMATTED_STRING",
            },
        )
        value_ranges = response.get("valueRanges", [])
        stats = {
            month: build_month_stats(
                month,
                source_name,
                value_ranges[index].get("values", [])
                if index < len(value_ranges)
                else [],
            )
            for index, (month, source_name) in enumerate(zip(months, source_names))
        }

        current = self.spreadsheet.values_batch_get(
            [
                f"'{SUMMARY_SHEET}'!B1",
                f"'{SUMMARY_SHEET}'!D1",
                f"'{SUMMARY_SHEET}'!F1",
                f"'{SUMMARY_SHEET}'!H1",
                f"'{SUMMARY_SHEET}'!K1",
                f"'{SUMMARY_SHEET}'!A4",
                f"'{SUMMARY_SHEET}'!Q1:Q1000",
                f"'{SUMMARY_SHEET}'!B2",
            ],
            params={
                "valueRenderOption": "FORMULA",
                "dateTimeRenderOption": "FORMATTED_STRING",
            },
        ).get("valueRanges", [])
        cells = [
            _first_value(value_range.get("values", [])) for value_range in current[:6]
        ]
        q_values = current[6].get("values", []) if len(current) > 6 else []
        display_mode = (
            str(_first_value(current[7].get("values", []))).strip()
            if len(current) > 7
            else "ทั้งหมด"
        )
        if display_mode not in {"ทั้งหมด", "เฉพาะเกิน 80%"}:
            display_mode = "ทั้งหมด"
        q_dates = tuple(
            parsed.date().replace(day=1)
            for row in q_values[1:]
            if row
            if (parsed := parse_parking_datetime(row[0])) is not None
        )
        q_current = (
            parse_parking_datetime(q_values[0][0]).date().replace(day=1)
            if q_values and q_values[0] and parse_parking_datetime(q_values[0][0])
            else None
        )
        selected_parsed = parse_parking_datetime(cells[0])
        selected_month = (
            selected_parsed.date().replace(day=1)
            if selected_parsed and selected_parsed.date().replace(day=1) in months
            else current_month
        )

        expected_formulas = (
            first_or_last_date_formula("MIN"),
            first_or_last_date_formula("MAX"),
            '=IF(OR(D1="",F1=""),"",F1-D1+1)',
            '=IF(H1="","",ROUNDUP(H1*80%,0))',
            monthly_table_formula(),
        )
        reasons = []
        if tuple(cells[1:]) != expected_formulas:
            reasons.append(
                "summary formulas still read RawData directly or use the old row limit"
            )
        if q_current != current_month:
            reasons.append("Bangkok current-month marker is stale")
        if q_dates[: len(months)] != months:
            reasons.append("month dropdown does not list all Archive sheets")
        if (
            selected_parsed is None
            or selected_parsed.date().replace(day=1) not in months
        ):
            reasons.append("selected month is unavailable")

        metadata = self.spreadsheet.fetch_sheet_metadata(
            params={
                "includeGridData": True,
                "ranges": f"'{SUMMARY_SHEET}'!B1",
            }
        )
        validation_source = _validation_source(metadata)
        if _normalized_validation_range(validation_source) != (
            "MONTHLYRANKING!Q2:Q1000"
        ):
            reasons.append(
                "month dropdown points to a backup sheet instead of MonthlyRanking"
            )

        return MonthlyRankingPlan(
            current_month=current_month,
            selected_month=selected_month,
            display_mode=display_mode,
            months=months,
            stats=stats,
            needs_update=bool(reasons),
            reasons=tuple(reasons),
        )

    def execute(
        self,
        plan: MonthlyRankingPlan,
        *,
        now: datetime | None = None,
    ) -> MonthlyRankingResult:
        if not plan.needs_update:
            return MonthlyRankingResult(None, (), False)

        current = (now or datetime.now(BANGKOK)).astimezone(BANGKOK)
        worksheet = self.spreadsheet.worksheet(SUMMARY_SHEET)
        backup_name = f"Backup_MonthlyRanking_{current:%Y%m%d_%H%M%S}"
        backup = self.spreadsheet.duplicate_sheet(
            worksheet.id,
            new_sheet_name=backup_name,
        )
        self.logger.info("Backup created: %s", backup_name)

        try:
            self.spreadsheet.batch_update(
                {
                    "requests": build_update_requests(
                        worksheet.id,
                        current_month=plan.current_month,
                        selected_month=plan.selected_month,
                        months=plan.months,
                    )
                }
            )
            self._set_display_mode(worksheet.id, "ทั้งหมด")
            verify_months = []
            archive_months = [
                month for month in plan.months if month != plan.current_month
            ]
            if archive_months:
                verify_months.append(archive_months[0])
            if plan.stats[plan.current_month].period_days:
                verify_months.append(plan.current_month)
            if not verify_months:
                raise RuntimeError("No source month has valid parking data")

            for month in verify_months:
                self._set_selected_month(worksheet.id, month)
                self._wait_for_verification(plan.stats[month])
                self.logger.info(
                    "Verified %s: %s rows, %s cars, %s days",
                    plan.stats[month].source_sheet,
                    plan.stats[month].source_rows,
                    plan.stats[month].unique_cars,
                    plan.stats[month].period_days,
                )
            self._set_selected_month(worksheet.id, plan.selected_month)
            self._set_display_mode(worksheet.id, plan.display_mode)
        except Exception:
            self.logger.exception(
                "MonthlyRanking repair failed; restoring %s", backup_name
            )
            self.spreadsheet.batch_update(
                {
                    "requests": [
                        {
                            "copyPaste": {
                                "source": {
                                    "sheetId": backup.id,
                                    "startRowIndex": 0,
                                    "endRowIndex": worksheet.row_count,
                                    "startColumnIndex": 0,
                                    "endColumnIndex": worksheet.col_count,
                                },
                                "destination": {
                                    "sheetId": worksheet.id,
                                    "startRowIndex": 0,
                                    "endRowIndex": worksheet.row_count,
                                    "startColumnIndex": 0,
                                    "endColumnIndex": worksheet.col_count,
                                },
                                "pasteType": "PASTE_NORMAL",
                                "pasteOrientation": "NORMAL",
                            }
                        }
                    ]
                }
            )
            raise

        return MonthlyRankingResult(backup_name, tuple(verify_months), True)

    def rollback(self, backup_name: str) -> None:
        worksheet = self.spreadsheet.worksheet(SUMMARY_SHEET)
        backup = self.spreadsheet.worksheet(backup_name)
        self.spreadsheet.batch_update(
            {
                "requests": [
                    {
                        "copyPaste": {
                            "source": {
                                "sheetId": backup.id,
                                "startRowIndex": 0,
                                "endRowIndex": worksheet.row_count,
                                "startColumnIndex": 0,
                                "endColumnIndex": worksheet.col_count,
                            },
                            "destination": {
                                "sheetId": worksheet.id,
                                "startRowIndex": 0,
                                "endRowIndex": worksheet.row_count,
                                "startColumnIndex": 0,
                                "endColumnIndex": worksheet.col_count,
                            },
                            "pasteType": "PASTE_NORMAL",
                            "pasteOrientation": "NORMAL",
                        }
                    }
                ]
            }
        )

    def _set_selected_month(self, sheet_id: int, month: date) -> None:
        self.spreadsheet.batch_update(
            {
                "requests": [
                    _single_cell_request(sheet_id, 0, 1, number=_date_serial(month))
                ]
            }
        )

    def _set_display_mode(self, sheet_id: int, mode: str) -> None:
        self.spreadsheet.batch_update(
            {"requests": [_single_cell_request(sheet_id, 1, 1, text=mode)]}
        )

    def _wait_for_verification(self, expected: MonthStats) -> None:
        last_error: Exception | None = None
        for _ in range(20):
            values = (
                self.spreadsheet.values_batch_get(
                    [f"'{SUMMARY_SHEET}'!A1:O1000"],
                    params={
                        "valueRenderOption": "UNFORMATTED_VALUE",
                        "dateTimeRenderOption": "SERIAL_NUMBER",
                    },
                )
                .get("valueRanges", [{}])[0]
                .get("values", [])
            )
            try:
                verify_summary_values(values, expected)
                return
            except (RuntimeError, TypeError, ValueError) as exc:
                last_error = exc
                time.sleep(1)
        raise RuntimeError(f"MonthlyRanking did not recalculate: {last_error}")


def _single_cell_request(
    sheet_id: int,
    row: int,
    column: int,
    *,
    formula: str | None = None,
    number: float | None = None,
    text: str | None = None,
) -> dict[str, object]:
    if formula is not None:
        value = {"formulaValue": formula}
    elif text is not None:
        value = {"stringValue": text}
    else:
        value = {"numberValue": number}
    return {
        "updateCells": {
            "start": {"sheetId": sheet_id, "rowIndex": row, "columnIndex": column},
            "rows": [{"values": [{"userEnteredValue": value}]}],
            "fields": "userEnteredValue",
        }
    }


def _date_format_request(
    sheet_id: int,
    start_row: int,
    start_column: int,
    end_row: int,
    end_column: int,
) -> dict[str, object]:
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_column,
                "endColumnIndex": end_column,
            },
            "cell": {
                "userEnteredFormat": {
                    "numberFormat": {"type": "DATE", "pattern": "d/m/yyyy"}
                }
            },
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def _date_serial(value: date) -> float:
    return float((value - date(1899, 12, 30)).days)


def _serial_date(value: object) -> date | None:
    parsed = parse_parking_datetime(value)
    return parsed.date() if parsed else None


def _escape(name: str) -> str:
    return name.replace("'", "''")


def _first_value(values: list[list[object]]) -> object:
    return values[0][0] if values and values[0] else ""


def _validation_source(metadata: dict[str, object]) -> str:
    try:
        sheet = next(
            item
            for item in metadata.get("sheets", [])
            if item.get("properties", {}).get("title") == SUMMARY_SHEET
        )
        return str(
            sheet["data"][0]["rowData"][0]["values"][0]["dataValidation"]["condition"][
                "values"
            ][0]["userEnteredValue"]
        )
    except (KeyError, IndexError, StopIteration, TypeError):
        return ""


def _normalized_validation_range(value: str) -> str:
    return value.lstrip("=").replace("'", "").replace("$", "").upper()
