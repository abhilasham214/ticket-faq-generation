import pytest

from api._lib.csv_ingest import CsvValidationError, parse_tickets_csv

VALID_CSV = (
    "id,subject,description,resolution\n"
    "TCK-001,Cannot log in,Password rejected,Cleared session cookie\n"
    "TCK-002,Billed twice,Duplicate charge,Refunded duplicate charge\n"
)


def test_parses_valid_csv_into_rows():
    rows = parse_tickets_csv(VALID_CSV.encode("utf-8"))
    assert len(rows) == 2
    assert rows[0]["external_id"] == "TCK-001"
    assert rows[0]["subject"] == "Cannot log in"


def test_generates_external_id_when_missing():
    csv_text = "subject,description,resolution\nA,B,C\n"
    rows = parse_tickets_csv(csv_text.encode("utf-8"))
    assert rows[0]["external_id"] == "TCK-001"


def test_rejects_missing_required_columns():
    csv_text = "subject,description\nA,B\n"
    with pytest.raises(CsvValidationError, match="resolution"):
        parse_tickets_csv(csv_text.encode("utf-8"))


def test_rejects_empty_file():
    with pytest.raises(CsvValidationError):
        parse_tickets_csv(b"")


def test_skips_incomplete_rows_but_keeps_valid_ones():
    csv_text = (
        "subject,description,resolution\n"
        "A,B,C\n"
        ",missing subject,resolution\n"
        "D,E,F\n"
    )
    rows = parse_tickets_csv(csv_text.encode("utf-8"))
    assert len(rows) == 2


def test_raises_when_all_rows_incomplete():
    csv_text = "subject,description,resolution\n,,\n"
    with pytest.raises(CsvValidationError):
        parse_tickets_csv(csv_text.encode("utf-8"))


def test_ignores_unrecognized_extra_columns():
    csv_text = "subject,description,resolution,priority\nA,B,C,high\n"
    rows = parse_tickets_csv(csv_text.encode("utf-8"))
    assert len(rows) == 1
    assert "priority" not in rows[0]
