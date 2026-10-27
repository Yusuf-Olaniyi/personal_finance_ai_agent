from checks import run_checks, CHECK_NAMES, ungrounded_numbers
from schemas import (BudgetAnalysis, SpendingCategory, SpendingRecommendation, SavingsStrategy,
                     EmergencyFund, SavingsRecommendation, DebtReduction, PayoffPlans, PayoffPlan,
                     DebtRecommendation,AutomationTechnique)


def make_result(budget_recs=None, savings_recs=None, warnings=None, debt=None, debts=(),automation=None, surplus_after_debt=200000):
    cats = [SpendingCategory(category="Rent", amount=200000),
            SpendingCategory(category="Food", amount=100000)]
    if budget_recs is None:
        budget_recs = [SpendingRecommendation(category="Food", recommendation="Cook at home",
                                              potential_savings=20000)]
    if savings_recs is None:
        savings_recs = [SavingsRecommendation(goal="Emergency fund", amount=100000,
                                              rationale="Build a buffer")]
    return {
        "facts": {"total_expenses": 300000, "surplus": 200000, "debts": list(debts),
                  "categories": [c.model_dump() for c in cats],"surplus_after_debt": surplus_after_debt,"emergency_fund_target": 1800000, "current_savings": 0},
        "budget": BudgetAnalysis(total_expenses=300000, spending_categories=cats,
                                 recommendations=budget_recs),
        "savings": SavingsStrategy(emergency_fund=EmergencyFund(recommended_amount=1800000),
                                   recommendations=savings_recs,automation_techniques=automation or []),
        "debt": debt,
        "warnings": warnings or [],
    }


def make_debt(advice: str) -> DebtReduction:
    plan = PayoffPlan(total_interest=1000, months_to_payoff=5, monthly_payment=1000, order=["A"])
    return DebtReduction(
        total_debt=1000, payoff_plans=PayoffPlans(avalanche=plan, snowball=plan),
        recommendations=[DebtRecommendation(title="Plan", description=advice, impact="faster")])


def failed(result) -> set:
    return {c.name for c in run_checks(result) if not c.passed}


def test_good_result_passes_everything_and_names_match():
    checks = run_checks(make_result())
    assert [c.name for c in checks] == CHECK_NAMES
    assert all(c.passed for c in checks)


def test_saving_larger_than_category_fails():
    bad = [SpendingRecommendation(category="Food", recommendation="x", potential_savings=150000)]
    assert "savings_within_category" in failed(make_result(budget_recs=bad))


def test_unknown_category_fails():
    bad = [SpendingRecommendation(category="Gym", recommendation="x", potential_savings=1000)]
    assert "categories_known" in failed(make_result(budget_recs=bad))


def test_allocation_above_surplus_fails():
    bad = [SavingsRecommendation(goal="Goal", amount=250000)]
    assert "allocation_within_surplus" in failed(make_result(savings_recs=bad))


def test_dollar_sign_fails():
    bad = [SpendingRecommendation(category="Food", recommendation="Save $50 a month",
                                  potential_savings=1000)]
    assert "currency_is_rwf" in failed(make_result(budget_recs=bad))


def test_pipeline_warning_fails():
    assert "pipeline_clean" in failed(make_result(warnings=["Model error: rate limit"]))


def test_missing_debt_result_fails_when_user_has_debts():
    assert "debt_presence_correct" in failed(make_result(debts=[{"name": "A"}], debt=None))


def test_debt_advice_without_strategy_fails_and_with_strategy_passes():
    two = [{"name": "A"}, {"name": "B"}]
    assert "debt_names_strategy" in failed(make_result(debts=two, debt=make_debt("Pay more.")))
    assert not failed(make_result(debts=two, debt=make_debt("Use the avalanche method.")))

def test_empty_savings_advice_fails():
    assert "has_savings_advice" in failed(make_result(savings_recs=[]))

def test_user_with_debts_but_no_debt_advice_fails():
    r = make_result(debts=[{"name": "A"}], debt=make_debt("x"))
    r["debt"].recommendations.clear()
    assert "has_debt_advice" in failed(r)

def test_automation_above_allocation_fails():
    auto = [AutomationTechnique(name="Standing order", monthly_amount=500000)]
    assert "automation_within_allocation" in failed(make_result(automation=auto))


def test_automation_without_amount_fails():
    auto = [AutomationTechnique(name="Standing order")]
    assert "automation_within_allocation" in failed(make_result(automation=auto))


def test_recommendations_when_no_surplus_fail():
    assert "no_filler_when_no_surplus" in failed(make_result(surplus_after_debt=-10000))


def test_empty_savings_advice_is_fine_when_no_surplus():
    bad = failed(make_result(savings_recs=[], surplus_after_debt=-10000))
    assert "has_savings_advice" not in bad and "no_filler_when_no_surplus" not in bad


def test_agent_names_in_advice_fail():
    bad = [SpendingRecommendation(category="Food", recommendation="As the BudgetAnalysisAgent said",
                                  potential_savings=1000)]
    assert "no_agent_names" in failed(make_result(budget_recs=bad))


def test_invented_amount_is_reported_and_grounded_ones_are_not():
    bad = [SpendingRecommendation(category="Food", recommendation="You will have 777,000 RWF spare",
                                  potential_savings=1000)]
    assert 777000 in ungrounded_numbers(make_result(budget_recs=bad))
    ok = [SpendingRecommendation(category="Food", recommendation="Cut 20,000 RWF from the 100,000 you spend",
                                 potential_savings=20000)]
    assert ungrounded_numbers(make_result(budget_recs=ok)) == []