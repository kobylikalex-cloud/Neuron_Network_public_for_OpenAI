"""Rule-based CSV time-series checks independent of any economic feature model."""

from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Sequence

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FREQUENCIES = {"D", "W", "M", "Q", "Y"}


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    row: int | None = None


@dataclass
class ValidationReport:
    file_name: str
    rows_checked: int = 0
    error_count: int = 0
    warning_count: int = 0
    duplicate_timestamps: int = 0
    missing_observation_periods: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)
    issues_truncated: bool = False

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict:
        return {**asdict(self), "passed": self.passed}

    def add(self, severity: str, code: str, message: str, row: int | None, limit: int) -> None:
        if severity == "error":
            self.error_count += 1
        elif severity == "warning":
            self.warning_count += 1
        else:
            raise ValueError("Unsupported severity")
        if len(self.issues) < limit:
            self.issues.append(ValidationIssue(severity, code, message, row))
        else:
            self.issues_truncated = True


def _period_index(value: date, frequency: str) -> int:
    if frequency == "D":
        return value.toordinal()
    if frequency == "W":
        # Monday-aligned ISO weeks. Week boundaries are consistent across years.
        return (value.toordinal() - 1) // 7
    if frequency == "M":
        return value.year * 12 + value.month - 1
    if frequency == "Q":
        return value.year * 4 + (value.month - 1) // 3
    return value.year


def validate_csv(
    path: str | Path, *, timestamp_column: str, value_columns: Sequence[str],
    frequency: str | None = None, allow_missing_values: bool = False,
    allow_duplicate_timestamps: bool = False, require_sorted: bool = True,
    max_issues: int = 100,
) -> ValidationReport:
    """Check dates, duplicates, order, numeric values, and optional calendar gaps.

    CSV dates must be ISO YYYY-MM-DD. Nonempty numeric columns are checked with
    Python's Decimal; no economic assumptions or imputation are performed.
    Frequency uses calendar days/weeks/months/quarters/years; it is not a trading
    calendar and does not validate source release calendars.
    """
    if not timestamp_column.strip():
        raise ValueError("timestamp_column must not be empty")
    if not value_columns or not all(isinstance(name, str) and name.strip() for name in value_columns):
        raise ValueError("Specify at least one nonempty value column")
    if len(set(value_columns)) != len(value_columns) or timestamp_column in value_columns:
        raise ValueError("Value columns must be distinct from each other and timestamp")
    if frequency is not None and frequency not in _FREQUENCIES:
        raise ValueError("frequency must be one of D, W, M, Q, Y")
    if max_issues < 0:
        raise ValueError("max_issues must be nonnegative")

    source = Path(path)
    report = ValidationReport(file_name=source.name)
    seen_dates: set[date] = set()
    seen_periods: set[int] = set()
    previous_date: date | None = None

    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("CSV requires a header")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("CSV header contains duplicate column names")
        expected = [timestamp_column, *value_columns]
        missing = [name for name in expected if name not in reader.fieldnames]
        if missing:
            raise ValueError(f"Required CSV columns not found: {', '.join(missing)}")

        for row_number, row in enumerate(reader, start=2):
            report.rows_checked += 1
            if None in row:  # CSV row has extra columns beyond its header.
                report.add("error", "EXTRA_FIELDS", "CSV row contains extra fields", row_number, max_issues)
            if any(row.get(name) is None for name in expected):
                report.add("error", "SHORT_ROW", "CSV row has fewer fields than expected", row_number, max_issues)
            raw_date = (row.get(timestamp_column) or "").strip()
            parsed: date | None = None
            if not _DATE_PATTERN.fullmatch(raw_date):
                report.add("error", "INVALID_DATE", "Date must use YYYY-MM-DD", row_number, max_issues)
            else:
                try:
                    parsed = date.fromisoformat(raw_date)
                except ValueError:
                    report.add("error", "INVALID_DATE", "Calendar date is invalid", row_number, max_issues)

            if parsed is not None:
                if parsed in seen_dates:
                    report.duplicate_timestamps += 1
                    severity = "warning" if allow_duplicate_timestamps else "error"
                    report.add(severity, "DUPLICATE_DATE", "Duplicate timestamp", row_number, max_issues)
                seen_dates.add(parsed)
                if require_sorted and previous_date is not None and parsed < previous_date:
                    report.add("error", "UNSORTED_DATE", "Dates are not in ascending order", row_number, max_issues)
                previous_date = parsed
                if frequency:
                    seen_periods.add(_period_index(parsed, frequency))

            for column in value_columns:
                raw = (row.get(column) or "").strip()
                if not raw:
                    report.add(
                        "warning" if allow_missing_values else "error", "MISSING_VALUE",
                        f"Value is missing in column {column!r}", row_number, max_issues,
                    )
                    continue
                try:
                    numeric = Decimal(raw)
                except InvalidOperation:
                    report.add("error", "NON_NUMERIC", f"Non-numeric value in {column!r}", row_number, max_issues)
                    continue
                if not numeric.is_finite():
                    report.add("error", "NON_FINITE", f"Non-finite number in {column!r}", row_number, max_issues)

    if not report.rows_checked:
        report.add("error", "EMPTY_DATA", "CSV has no data rows", None, max_issues)

    if frequency and len(seen_periods) > 1:
        ordered = sorted(seen_periods)
        for previous, current in zip(ordered, ordered[1:]):
            gap = current - previous - 1
            if gap > 0:
                report.missing_observation_periods += gap
        if report.missing_observation_periods:
            report.add(
                "warning", "PERIOD_GAPS",
                f"Found {report.missing_observation_periods} missing calendar {frequency} periods",
                None, max_issues,
            )

    return report
