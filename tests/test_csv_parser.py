import pytest
from finance_coach.data.csv_parser import parse_expense_csv, CSVError


def test_messy_amounts_and_monthly_average():
    data = (
        "Date,Category,Amount\n"
        '2026-01-05,rent,"150,000"\n'
        "2026-01-09,Food,RWF 20000\n"
        "2026-02-05,Rent,150000\n"
        "2026-02-10,food,30000\n"
    ).encode("utf-8-sig")  # includes the BOM, like a real Excel export
    r = parse_expense_csv(data)
    assert r["category_totals"] == {"Rent": 300000, "Food": 50000}
    assert r["months_covered"] == 2
    assert r["monthly_expenses"] == {"Rent": 150000, "Food": 25000}
    assert r["skipped"] == []


def test_bad_rows_are_skipped_not_fatal():
    data = (
        "Date,Category,Amount\n"
        "2026-01-05,Rent,100000\n"
        "not-a-date,Food,5000\n"
        "2026-01-06,Food,abc\n"
        "2026-01-07,Food,-500\n"
    ).encode()
    r = parse_expense_csv(data)
    assert r["category_totals"] == {"Rent": 100000}
    assert len(r["skipped"]) == 3


def test_missing_column_raises():
    with pytest.raises(CSVError, match="Category"):
        parse_expense_csv(b"Date,Amount\n2026-01-01,1000\n")


def test_empty_file_raises():
    with pytest.raises(CSVError):
        parse_expense_csv(b"Date,Category,Amount\n")