import pytest
from schemas import Debt
from payoff import simulate_payoff, build_payoff_plans


def test_zero_interest_is_simple_division():
    d = [Debt(name="A", amount=100000, interest_rate=0, min_payment=25000)]
    plan = simulate_payoff(d, 25000, "avalanche")
    assert plan.months_to_payoff == 4
    assert plan.total_interest == 0
    assert plan.order == ["A"]


def test_single_debt_matches_amortization_math():
    # 100,000 at 12%/yr, paying 10,000/month.
    # Worked by hand: 10 full payments, then a final ~5,898 in month 11.
    d = [Debt(name="A", amount=100000, interest_rate=12, min_payment=10000)]
    plan = simulate_payoff(d, 10000, "avalanche")
    assert plan.months_to_payoff == 11
    assert abs(plan.total_interest - 5898) <= 2


def test_avalanche_beats_snowball_and_orders_differ():
    debts = [
        Debt(name="A", amount=50000, interest_rate=30, min_payment=2000),
        Debt(name="B", amount=10000, interest_rate=5, min_payment=1000),
    ]
    plans = build_payoff_plans(debts, 10000)
    assert plans.avalanche.order[0] == "A"
    assert plans.snowball.order[0] == "B"
    assert plans.avalanche.total_interest < plans.snowball.total_interest


def test_budget_below_minimums_raises():
    d = [Debt(name="A", amount=100000, interest_rate=10, min_payment=5000)]
    with pytest.raises(ValueError, match="minimum"):
        simulate_payoff(d, 4000, "avalanche")


def test_unpayable_debt_raises():
    # 5%/month interest = 50,000, but we only pay 10,000
    d = [Debt(name="A", amount=1_000_000, interest_rate=60, min_payment=10000)]
    with pytest.raises(ValueError, match="50 years"):
        simulate_payoff(d, 10000, "avalanche")


def test_no_debts_returns_zero_plan():
    plan = simulate_payoff([], 50000, "snowball")
    assert plan.months_to_payoff == 0 and plan.order == []


def test_duplicate_names_rejected():
    d = [Debt(name="A", amount=1000, interest_rate=5), Debt(name="A", amount=2000, interest_rate=5)]
    with pytest.raises(ValueError, match="unique"):
        simulate_payoff(d, 1000, "avalanche")