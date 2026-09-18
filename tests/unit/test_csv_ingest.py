import pytest

from api._lib.csv_ingest import CsvValidationError, parse_tickets_csv

VALID_CSV = (
    "id,subject,description,resolution\n"
    "TCK-001,Cannot log in,Password rejected,Cleared session cookie\n"
    "TCK-002,Billed twice,Duplicate charge,Refunded duplicate charge\n"
    "TCK-003,API key expired,Key stopped working,Issued a new key\n"
)


def test_parses_valid_csv_into_rows():
    rows = parse_tickets_csv(VALID_CSV.encode("utf-8"))
    assert len(rows) == 3
    assert rows[0]["external_id"] == "TCK-001"
    assert rows[0]["subject"] == "Cannot log in"
    assert rows[0]["description"] == "Password rejected"


def test_accepts_title_and_ticket_id_column_aliases():
    csv_text = (
        "ticket_id,title,resolution\n"
        "T1,Cannot log in,Cleared session cookie\n"
        "T2,Billed twice,Refunded duplicate charge\n"
        "T3,API key expired,Issued a new key\n"
    )
    rows = parse_tickets_csv(csv_text.encode("utf-8"))
    assert len(rows) == 3
    assert rows[0]["external_id"] == "T1"
    assert rows[0]["description"] == ""


def test_rejects_missing_resolution_column():
    csv_text = "id,subject,description\nT1,A,B\nT2,C,D\nT3,E,F\n"
    with pytest.raises(CsvValidationError, match="resolution"):
        parse_tickets_csv(csv_text.encode("utf-8"))


def test_rejects_missing_subject_column():
    csv_text = "id,resolution\nT1,B\nT2,D\nT3,F\n"
    with pytest.raises(CsvValidationError, match="subject"):
        parse_tickets_csv(csv_text.encode("utf-8"))


def test_rejects_missing_id_column():
    csv_text = "subject,resolution\nA,B\nC,D\nE,F\n"
    with pytest.raises(CsvValidationError, match="id"):
        parse_tickets_csv(csv_text.encode("utf-8"))


def test_rejects_empty_file():
    with pytest.raises(CsvValidationError):
        parse_tickets_csv(b"")


def test_skips_rows_missing_a_required_value_but_keeps_valid_ones():
    csv_text = (
        "id,subject,resolution\n"
        "T1,A,B\n"
        ",missing id,C\n"
        "T2,D,E\n"
        "T3,F,G\n"
    )
    rows = parse_tickets_csv(csv_text.encode("utf-8"))
    assert len(rows) == 3


def test_ignores_unrecognized_extra_columns():
    csv_text = (
        "id,subject,resolution,priority\n"
        "T1,A,B,high\n"
        "T2,C,D,low\n"
        "T3,E,F,low\n"
    )
    rows = parse_tickets_csv(csv_text.encode("utf-8"))
    assert len(rows) == 3
    assert "priority" not in rows[0]


def test_rejects_when_fewer_than_minimum_valid_tickets():
    csv_text = "id,subject,resolution\nT1,A,B\nT2,C,D\n"
    with pytest.raises(CsvValidationError, match="least"):
        parse_tickets_csv(csv_text.encode("utf-8"))
