import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from schemas import BudgetAnalysis, DebtReduction


def spending_pie(budget: BudgetAnalysis) -> go.Figure:
    cats = budget.spending_categories
    fig = px.pie(
        names=[c.category for c in cats],
        values=[c.amount for c in cats],
        title="Monthly spending by category (RWF)",
        hole=0.35,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_traces(textinfo="label+percent")
    return fig


def income_vs_expenses(income: int, expenses: int) -> go.Figure:
    surplus = income - expenses
    label = "surplus" if surplus >= 0 else "deficit"
    fig = go.Figure(go.Bar(
        x=["Income", "Expenses"],
        y=[income, expenses],
        marker_color=["#2e7d32", "#c62828"],
        text=[f"{income:,}", f"{expenses:,}"],
        textposition="auto",
    ))
    fig.update_layout(
        title=f"Monthly income vs expenses ({label}: RWF {abs(surplus):,})",
        yaxis_title="RWF",
    )
    return fig


def debt_comparison(debt: DebtReduction) -> go.Figure:
    a, s = debt.payoff_plans.avalanche, debt.payoff_plans.snowball
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("Total interest paid (RWF)", "Months to debt-free"))
    fig.add_trace(go.Bar(x=["Avalanche", "Snowball"],
                         y=[a.total_interest, s.total_interest],
                         marker_color=["#1565c0", "#ef6c00"]), row=1, col=1)
    fig.add_trace(go.Bar(x=["Avalanche", "Snowball"],
                         y=[a.months_to_payoff, s.months_to_payoff],
                         marker_color=["#1565c0", "#ef6c00"]), row=1, col=2)
    fig.update_layout(showlegend=False, title="Avalanche vs snowball")
    return fig