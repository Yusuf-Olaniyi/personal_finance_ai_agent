from typing import Dict, List
from schemas import Debt, SpendingCategory


def compute_facts(
    monthly_income: int,
    expenses: Dict[str, int],
    debts: List[Debt],
    monthly_debt_budget: int,
    current_savings: int = 0,
) -> dict:
    total = sum(expenses.values())
    categories = [
        SpendingCategory(
            category=name,
            amount=amount,
            percentage=round(amount / total * 100, 1) if total else 0,
        )
        for name, amount in sorted(expenses.items(), key=lambda kv: kv[1], reverse=True)
    ]
    surplus = monthly_income - total  # negative means a deficit
    return {
        "monthly_income": monthly_income,
        "total_expenses": total,
        "surplus": surplus,
        "savings_rate_pct": round(surplus / monthly_income * 100, 1) if monthly_income else 0,
        "categories": [c.model_dump() for c in categories],
        "emergency_fund_target": total * 6,   # 6 months of expenses
        "current_savings": current_savings,
        "debts": [d.model_dump() for d in debts],
        "total_debt": sum(d.amount for d in debts),
        "monthly_debt_budget": monthly_debt_budget,
        "surplus_after_debt": surplus - monthly_debt_budget,
    }