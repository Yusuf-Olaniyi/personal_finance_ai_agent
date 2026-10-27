from typing import List
from finance_coach.schemas import Debt, PayoffPlan, PayoffPlans

MAX_MONTHS = 600  # 50 years; beyond this we treat the debt as unpayable


def _priority(balances: dict, rates: dict, strategy: str) -> List[str]:
    if strategy == "avalanche":      # highest interest rate first
        return sorted(balances, key=lambda n: rates[n], reverse=True)
    return sorted(balances, key=lambda n: balances[n])  # snowball: smallest balance first


def simulate_payoff(debts: List[Debt], monthly_budget: int, strategy: str) -> PayoffPlan:
    if strategy not in ("avalanche", "snowball"):
        raise ValueError(f"Unknown strategy: {strategy}")

    active = [d for d in debts if d.amount > 0]
    if len({d.name for d in active}) != len(active):
        raise ValueError("Debt names must be unique")
    if not active:
        return PayoffPlan(total_interest=0, months_to_payoff=0,
                          monthly_payment=monthly_budget, order=[])

    min_total = sum(d.min_payment for d in active)
    if monthly_budget < min_total:
        raise ValueError(
            f"Monthly budget {monthly_budget} is below total minimum payments {min_total}"
        )

    balances = {d.name: float(d.amount) for d in active}
    rates = {d.name: d.interest_rate / 100 / 12 for d in active}
    minimums = {d.name: d.min_payment for d in active}

    total_interest = 0.0
    order: List[str] = []
    months = 0

    while balances and months < MAX_MONTHS:
        months += 1

        # 1. accrue interest
        for name in balances:
            interest = balances[name] * rates[name]
            balances[name] += interest
            total_interest += interest

        # 2. pay minimums
        available = float(monthly_budget)
        for name in list(balances):
            pay = min(minimums[name], balances[name])
            balances[name] -= pay
            available -= pay

        # 3. send the rest to the target debt(s)
        for name in _priority(balances, rates, strategy):
            if available <= 0:
                break
            pay = min(available, balances[name])
            balances[name] -= pay
            available -= pay

        # 4. retire paid-off debts
        for name in list(balances):
            if balances[name] <= 0.005:
                del balances[name]
                order.append(name)

    if balances:
        raise ValueError("Debts cannot be paid off within 50 years at this monthly budget")

    return PayoffPlan(
        total_interest=round(total_interest),
        months_to_payoff=months,
        monthly_payment=monthly_budget,
        order=order,
    )


def build_payoff_plans(debts: List[Debt], monthly_budget: int) -> PayoffPlans:
    return PayoffPlans(
        avalanche=simulate_payoff(debts, monthly_budget, "avalanche"),
        snowball=simulate_payoff(debts, monthly_budget, "snowball"),
    )