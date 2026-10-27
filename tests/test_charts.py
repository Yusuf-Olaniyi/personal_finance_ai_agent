from finance_coach.ui.charts import spending_pie, income_vs_expenses
from finance_coach.schemas import BudgetAnalysis, SpendingCategory


def test_pie_has_one_slice_per_category():
    b = BudgetAnalysis(
        total_expenses=300000,
        spending_categories=[
            SpendingCategory(category="Rent", amount=200000),
            SpendingCategory(category="Food", amount=100000),
        ],
    )
    fig = spending_pie(b)
    assert list(fig.data[0].labels) == ["Rent", "Food"]
    assert list(fig.data[0].values) == [200000, 100000]


def test_deficit_is_labelled():
    fig = income_vs_expenses(100000, 150000)
    assert "deficit" in fig.layout.title.text