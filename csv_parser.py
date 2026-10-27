import io
import re
import pandas as pd

REQUIRED = {"date": "Date", "category": "Category", "amount": "Amount"}


class CSVError(ValueError):
    """The file as a whole is unusable (bad format, missing columns, empty)."""


def _to_rwf(raw) -> int:
    cleaned = re.sub(r"[^\d.\-]", "", str(raw))   # drops 'RWF', spaces, commas
    if cleaned in ("", ".", "-"):
        raise ValueError(f"not a number: {raw!r}")
    return round(float(cleaned))


def parse_expense_csv(file_bytes: bytes) -> dict:
    try:
        # utf-8-sig strips the invisible BOM that Excel adds to CSV files
        df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8-sig", dtype=str)
    except Exception as e:
        raise CSVError(f"Could not read the file as CSV: {e}") from e

    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [name for key, name in REQUIRED.items() if key not in df.columns]
    if missing:
        raise CSVError(f"Missing required columns: {', '.join(missing)}")
    if df.empty:
        raise CSVError("The file has no rows")

    transactions, skipped = [], []
    for i, row in df.iterrows():
        line = i + 2  # +1 for the header row, +1 because humans count from 1
        try:
            if pd.isna(row["date"]) or pd.isna(row["category"]) or pd.isna(row["amount"]):
                raise ValueError("empty cell")
            date = pd.to_datetime(row["date"])
            category = str(row["category"]).strip().title()
            amount = _to_rwf(row["amount"])
            if amount < 0:
                raise ValueError("negative amount")
            transactions.append({"date": date, "category": category, "amount": amount})
        except (ValueError, TypeError) as e:
            skipped.append(f"Row {line}: {e}")

    if not transactions:
        raise CSVError("No valid rows found. " + "; ".join(skipped[:3]))

    months = len({(t["date"].year, t["date"].month) for t in transactions})
    totals: dict = {}
    for t in transactions:
        totals[t["category"]] = totals.get(t["category"], 0) + t["amount"]

    return {
        "transactions": [{**t, "date": t["date"].strftime("%Y-%m-%d")} for t in transactions],
        "category_totals": totals,
        "months_covered": months,
        "monthly_expenses": {c: round(a / months) for c, a in totals.items()},
        "skipped": skipped,
    }