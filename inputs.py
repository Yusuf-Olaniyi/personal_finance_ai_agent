import pandas as pd
from pydantic import ValidationError
from schemas import Debt

EXPENSE_COLS = ["Category", "Amount (RWF)"]
DEBT_COLS = ["Name", "Balance (RWF)", "Interest rate (% / year)", "Min payment (RWF)"]


def df_to_expenses(df: pd.DataFrame) -> dict:
    """Editable table -> {category: monthly RWF}. Blank rows are ignored."""
    expenses: dict = {}
    for _, row in df.iterrows():
        cat, amt = row.get("Category"), row.get("Amount (RWF)")
        if pd.isna(cat) or not str(cat).strip() or pd.isna(amt):
            continue
        amount = round(float(amt))
        if amount < 0:
            raise ValueError(f"Negative amount for {cat}")
        key = str(cat).strip().title()
        expenses[key] = expenses.get(key, 0) + amount
    return expenses


def df_to_debts(df: pd.DataFrame):
    """Editable table -> (valid Debt objects, list of human-readable errors)."""
    debts, errors, seen = [], [], set()
    for i, row in df.iterrows():
        name = row.get("Name")
        if pd.isna(name) or not str(name).strip():
            continue
        name = str(name).strip()
        if name.lower() in seen:
            errors.append(f"Debt row {i + 1}: duplicate name '{name}'")
            continue
        try:
            min_pay = row.get("Min payment (RWF)")
            debts.append(Debt(
                name=name,
                amount=row.get("Balance (RWF)"),
                interest_rate=row.get("Interest rate (% / year)"),
                min_payment=0 if pd.isna(min_pay) else min_pay,
            ))
            seen.add(name.lower())
        except (ValidationError, ValueError, TypeError) as e:
            errors.append(f"Debt row {i + 1} ('{name}'): invalid values ({type(e).__name__})")
    return debts, errors