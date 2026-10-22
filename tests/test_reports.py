import csv

import pytest

from ev_digital_twin.reports import write_csv_report


def test_write_csv_report_creates_parent_directory(tmp_path):
    path = tmp_path / "reports" / "summary.csv"

    assert write_csv_report(str(path), [{"seed": 42, "score": 1.5}]) == str(path)
    with path.open(newline="", encoding="utf-8") as report:
        rows = list(csv.DictReader(report))

    assert rows == [{"seed": "42", "score": "1.5"}]


def test_write_csv_report_rejects_inconsistent_columns(tmp_path):
    with pytest.raises(ValueError, match="same columns"):
        write_csv_report(str(tmp_path / "bad.csv"), [{"a": 1}, {"b": 2}])
