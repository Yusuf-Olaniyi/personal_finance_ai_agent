import pandas as pd
import streamlit as st

from finance_coach.ui.charts import debt_comparison, income_vs_expenses, spending_pie


def rwf(x) -> str:
    return f"{x:,.0f} RWF"

def show_budget(res):
    b, f = res["budget"], res["facts"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Income", rwf(f["monthly_income"]))
    m2.metric("Expenses", rwf(f["total_expenses"]))
    m3.metric("Surplus" if f["surplus"] >= 0 else "Deficit", rwf(abs(f["surplus"])))
    g1, g2 = st.columns(2)
    g1.plotly_chart(spending_pie(b), width="stretch")
    g2.plotly_chart(income_vs_expenses(f["monthly_income"], f["total_expenses"]), width="stretch")
    st.subheader("Recommendations")
    if not b.recommendations:
        st.info("No budget recommendations were produced.")
    for r in b.recommendations:
        st.markdown(f"**{r.category}**: {r.recommendation}  \n"
                    f"*Potential saving: {rwf(r.potential_savings)} / month*")


def show_savings(res):
    s, f = res["savings"], res["facts"]
    e1, e2 = st.columns(2)
    e1.metric("Emergency fund target (6 months)", rwf(s.emergency_fund.recommended_amount))
    e2.metric("Current savings", rwf(s.emergency_fund.current_amount))
    if s.emergency_fund.current_status:
        st.write(s.emergency_fund.current_status)
    if f["surplus_after_debt"] <= 0:
        st.warning(
            "After your expenses and debt payments there is no money left to save "
            f"(shortfall: {rwf(abs(f['surplus_after_debt']))} per month). "
            "Start with the Budget tab: closing this gap comes before any savings plan.")
    if s.recommendations:
        st.subheader("Where to put your surplus")
        for r in s.recommendations:
            st.markdown(f"**{r.goal}**: {rwf(r.amount)}  \n{r.rationale}")
    if s.automation_techniques:
        st.subheader("Automation ideas")
        for t in s.automation_techniques:
            st.markdown(f"**{t.name}** ({rwf(t.monthly_amount)} / month): {t.description}")
    if not (s.recommendations or s.automation_techniques) and f["surplus_after_debt"] > 0:
        st.info("No savings advice was produced.")


def show_debt(res):
    d = res["debt"]
    if d is None:
        st.info("No debt plan (no debts entered, or the plan could not be calculated).")
        return
    st.metric("Total debt", rwf(d.total_debt))
    st.plotly_chart(debt_comparison(d), width="stretch")
    a, s = d.payoff_plans.avalanche, d.payoff_plans.snowball
    st.dataframe(pd.DataFrame({
        "Strategy": ["Avalanche (highest rate first)", "Snowball (smallest balance first)"],
        "Months": [a.months_to_payoff, s.months_to_payoff],
        "Total interest (RWF)": [a.total_interest, s.total_interest],
        "Payoff order": [" → ".join(a.order), " → ".join(s.order)],
    }), width="stretch", hide_index=True)
    st.subheader("Recommendations")
    if not d.recommendations:
        st.info("No debt recommendations were produced.")
    for r in d.recommendations:
        st.markdown(f"**{r.title}**: {r.description}  \n*Impact: {r.impact}*")

