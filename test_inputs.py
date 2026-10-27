import pandas as pd
import pytest
from inputs import df_to_expenses, df_to_debts


def test_expenses_merge_and_skip_blanks():
    df = pd.DataFrame({"Category": ["rent", "Rent", None, "Food"],
                       "Amount (RWF)": [100000, 50000, 999, None]})
    assert df_to_expenses(df) == {"Rent": 150000}


def test_negative_expense_raises():
    df = pd.DataFrame({"Category": ["Rent"], "Amount (RWF)": [-5]})
    with pytest.raises(ValueError):
        df_to_expenses(df)


def test_debts_valid_and_invalid_rows():
    df = pd.DataFrame({
        "Name": ["Loan", "Bad", None],
        "Balance (RWF)": [100000, 50000, 1],
        "Interest rate (% / year)": [15, 150, 5],
        "Min payment (RWF)": [5000, None, None],
    })
    debts, errors = df_to_debts(df)
    assert [d.name for d in debts] == ["Loan"]
    assert len(errors) == 1


def test_duplicate_debt_names_reported():
    df = pd.DataFrame({
        "Name": ["A", "a"], "Balance (RWF)": [1000, 2000],
        "Interest rate (% / year)": [5, 5], "Min payment (RWF)": [0, 0],
    })
    debts, errors = df_to_debts(df)
    assert len(debts) == 1 and "duplicate" in errors[0]