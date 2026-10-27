import pytest
from pydantic import ValidationError
from finance_coach.schemas import BudgetAnalysis, Debt, DebtReduction


def test_money_coerces_messy_llm_output():
    b = BudgetAnalysis(total_expenses="RWF 450,000")
    assert b.total_expenses == 450000
    assert BudgetAnalysis(total_expenses=450000.0).total_expenses == 450000
    assert BudgetAnalysis(total_expenses=450000.6).total_expenses == 450001


def test_missing_optional_fields_use_defaults():
    b = BudgetAnalysis(total_expenses=1000)
    assert b.spending_categories == []
    assert b.monthly_income is None


def test_negative_money_rejected():
    with pytest.raises(ValidationError):
        BudgetAnalysis(total_expenses=-5)


def test_interest_rate_bounds():
    with pytest.raises(ValidationError):
        Debt(name="Loan", amount=100000, interest_rate=150)


def test_required_fields_enforced():
    with pytest.raises(ValidationError):
        DebtReduction(total_debt=0)  # payoff_plans is required


def test_parses_realistic_llm_json():
    raw = """{"total_expenses": "320,000",
              "monthly_income": 500000.0,
              "spending_categories": [{"category": "Rent", "amount": 150000}]}"""
    b = BudgetAnalysis.model_validate_json(raw)
    assert b.spending_categories[0].amount == 150000