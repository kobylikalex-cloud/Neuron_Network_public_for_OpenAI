"""Contract tests: all test observations are invented."""

from pathlib import Path

import pytest

from edge_provenance.quality import validate_csv


def sample(tmp_path: Path, content: str) -> Path:
    dest = tmp_path / "sample.csv"
    dest.write_text(content, encoding="utf-8")
    return dest


def check(path, **kwargs):
    return validate_csv(path, timestamp_column="date", value_columns=["value"], **kwargs)


def test_valid_monthly_with_calendar_month_end(tmp_path):
    r = check(sample(tmp_path, "date,value\n2026-01-31,1\n2026-02-28,2\n2026-03-31,3\n"), frequency="M")
    assert r.passed and r.rows_checked == 3 and r.missing_observation_periods == 0
    assert not r.issues


def test_duplicates_rejected_by_default(tmp_path):
    r = check(sample(tmp_path, "date,value\n2026-01-01,3\n2026-01-01,4\n"))
    assert not r.passed and r.duplicate_timestamps == 1
    assert r.issues[0].code == "DUPLICATE_DATE"


def test_duplicates_can_be_warnings(tmp_path):
    r = check(sample(tmp_path, "date,value\n2026-01-01,3\n2026-01-01,4\n"), allow_duplicate_timestamps=True)
    assert r.passed and r.warning_count == 1


def test_unsorted_dates(tmp_path):
    path = sample(tmp_path, "date,value\n2026-02-01,1\n2026-01-01,2\n")
    assert not check(path).passed
    assert check(path, require_sorted=False).passed


@pytest.mark.parametrize("bad", ["2026-02-30", "02/01/2026", "", "2026-3-1", "2026-01-01T00:00:00"])
def test_bad_dates_are_rejected(tmp_path, bad):
    r = check(sample(tmp_path, f"date,value\n{bad},12\n"))
    assert not r.passed and r.issues[0].code == "INVALID_DATE"


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "n/a", "1,2"])
def test_nonfinite_or_nonnumeric_values(tmp_path, bad):
    path = sample(tmp_path, f"date,value\n2026-01-01,{bad}\n")
    assert not check(path).passed


def test_missing_numeric_values_can_be_warning(tmp_path):
    path = sample(tmp_path, "date,value\n2026-01-01,\n")
    assert not check(path).passed
    r = check(path, allow_missing_values=True)
    assert r.passed and r.warning_count == 1


@pytest.mark.parametrize("frequency,dates,missing", [
    ("D", ["2026-01-01", "2026-01-04"], 2),
    ("W", ["2026-01-05", "2026-01-19"], 1),
    ("M", ["2026-01-31", "2026-04-30"], 2),
    ("Q", ["2026-01-01", "2026-10-01"], 2),
    ("Y", ["2024-12-31", "2026-12-31"], 1),
])
def test_frequency_gaps(tmp_path, frequency, dates, missing):
    path = sample(tmp_path, f"date,value\n{dates[0]},1\n{dates[1]},2\n")
    r = check(path, frequency=frequency)
    assert r.passed and r.missing_observation_periods == missing
    assert "PERIOD_GAPS" in [i.code for i in r.issues]


def test_no_synthetic_gaps_with_mismatched_day_numbers(tmp_path):
    path = sample(tmp_path, "date,value\n2026-01-01,1\n2026-02-28,2\n")
    assert check(path, frequency="M").missing_observation_periods == 0


def test_multiple_value_columns_and_bom(tmp_path):
    path = tmp_path / "other.csv"
    path.write_text("\ufeffdate,first,second\n2026-01-01,1,2\n", encoding="utf-8")
    r = validate_csv(path, timestamp_column="date", value_columns=["first", "second"])
    assert r.passed


def test_extra_and_short_fields_rejected(tmp_path):
    for data in ("date,value\n2026-01-01,1,2\n", "date,value\n2026-01-01\n"):
        assert not check(sample(tmp_path, data)).passed


def test_column_validation_and_duplicate_headers(tmp_path):
    path = sample(tmp_path, "date,value\n2026-01-01,1\n")
    with pytest.raises(ValueError, match="not found"):
        validate_csv(path, timestamp_column="date", value_columns=["missing"])
    with pytest.raises(ValueError, match="distinct"):
        validate_csv(path, timestamp_column="date", value_columns=["date"])
    with pytest.raises(ValueError, match="frequency"):
        check(path, frequency="B")
    path = sample(tmp_path, "date,value,value\n2026-01-01,1,2\n")
    with pytest.raises(ValueError, match="duplicate column"):
        check(path)


def test_issue_truncation_preserves_summary(tmp_path):
    path = sample(tmp_path, "date,value\n" + "2026-01-01,NaN\n" * 20)
    r = check(path, max_issues=3)
    assert r.error_count == 39 and len(r.issues) == 3 and r.issues_truncated


def test_empty_csv_is_not_success(tmp_path):
    r = check(sample(tmp_path, "date,value\n"))
    assert not r.passed and r.issues[0].code == "EMPTY_DATA"


def test_missing_header(tmp_path):
    with pytest.raises(ValueError, match="header"):
        check(sample(tmp_path, ""))
