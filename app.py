import asyncio
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from agents import FinanceAdvisor
from charts import debt_comparison, income_vs_expenses, spending_pie
from csv_parser import CSVError, parse_expense_csv
from inputs import DEBT_COLS, df_to_debts, df_to_expenses

load_dotenv()
BASE = Path(__file__).parent

st.set_page_config(page_title="AI Financial Coach", page_icon="💰", layout="wide")
st.markdown(f"<style>{(BASE / 'style.css').read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True)


def rwf(x) -> str:
    return f"{x:,.0f} RWF"


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("### 🔑 Your AI key")
    user_key = st.text_input(
        "Groq API key", type="password", placeholder="gsk_...",
        help="Get a free key at console.groq.com. It is used only for your analysis "
             "in this session and is not saved by this app.")
    api_key = user_key.strip() or os.getenv("GROQ_API_KEY")
    if api_key:
        st.success("Key ready")
    else:
        st.info("Paste a free Groq key to run the analysis.")
    st.caption(f"Model: {os.getenv('LLM_MODEL', 'groq/openai/gpt-oss-120b')}")
    st.divider()
    st.markdown("### 📄 CSV template")
    st.markdown("Columns: **Date**, **Category**, **Amount**. Several months are fine.")
    st.download_button("Download sample CSV", (BASE / "sample_expenses.csv").read_bytes(),
                       file_name="expense_template.csv", mime="text/csv")

# --------------------------------------------------------------------- hero
st.markdown(
    '<div class="hero"><h1>💰 AI Financial Coach</h1>'
    "<p>Three AI agents turn your income, spending and debts into a clear plan. "
    "Code does all the maths, so the numbers are reliable, and the AI explains what to do. "
    "All amounts are in RWF.</p></div>",
    unsafe_allow_html=True)

# --------------------------------------------------------------- input form
problems: list = []

st.subheader("1 · Income and savings")
c1, c2 = st.columns(2)
income = c1.number_input("Monthly income (RWF)", min_value=0, step=10_000, value=0)
savings_now = c2.number_input("Current savings (RWF)", min_value=0, step=10_000, value=0)

st.subheader("2 · Monthly expenses")
mode = st.radio("How would you like to enter expenses?",
                ["Enter manually", "Upload CSV"], horizontal=True)

expenses: dict = {}
if mode == "Upload CSV":
    uploaded = st.file_uploader("Expense CSV", type="csv")
    if uploaded is not None:
        try:
            parsed = parse_expense_csv(uploaded.getvalue())
            expenses = parsed["monthly_expenses"]
            st.caption(f"Read {len(parsed['transactions'])} transactions covering "
                       f"{parsed['months_covered']} month(s). Amounts below are monthly averages.")
            if parsed["skipped"]:
                with st.expander(f"{len(parsed['skipped'])} row(s) skipped"):
                    for s in parsed["skipped"]:
                        st.write(s)
            st.dataframe(pd.DataFrame(
                {"Category": list(expenses), "Monthly (RWF)": list(expenses.values())}),
                width="stretch", hide_index=True)
        except CSVError as e:
            problems.append(str(e))
else:
    exp_df = st.data_editor(
        pd.DataFrame({"Category": ["Rent", "Food"], "Amount (RWF)": [None, None]}),
        num_rows="dynamic", key="expense_editor", width="stretch",
        column_config={"Amount (RWF)": st.column_config.NumberColumn(
            min_value=0, step=1000, format="%d")},
    )
    try:
        expenses = df_to_expenses(exp_df)
    except ValueError as e:
        problems.append(str(e))

st.subheader("3 · Debts (optional)")
debt_df = st.data_editor(
    pd.DataFrame({c: pd.Series(dtype="object" if c == "Name" else "float") for c in DEBT_COLS}),
    num_rows="dynamic", key="debt_editor", width="stretch",
    column_config={
        "Balance (RWF)": st.column_config.NumberColumn(min_value=0, step=10_000, format="%d"),
        "Interest rate (% / year)": st.column_config.NumberColumn(min_value=0, max_value=100, step=0.5),
        "Min payment (RWF)": st.column_config.NumberColumn(min_value=0, step=1000, format="%d"),
    },
)
debts, debt_errors = df_to_debts(debt_df)
problems += debt_errors

debt_budget = 0
if debts:
    min_total = sum(d.min_payment for d in debts)
    debt_budget = st.number_input(
        "Monthly amount you can put toward debt (RWF)",
        min_value=0, step=5_000, value=max(min_total, 0),
        help="Must cover at least the sum of minimum payments.")
    if debt_budget < min_total:
        problems.append(f"Debt budget ({rwf(debt_budget)}) is below total minimum payments ({rwf(min_total)}).")

if income <= 0:
    problems.append("Enter your monthly income.")
if not expenses:
    problems.append("Add at least one expense.")
if not api_key:
    problems.append("Paste your Groq API key in the sidebar.")

for p in problems:
    st.warning(p)

# ----------------------------------------------------------------- analysis
if st.button("Analyse my finances", type="primary", disabled=bool(problems)):
    advisor = FinanceAdvisor(api_key=api_key)  # fresh per run: avoids closed-event-loop issues
    try:
        with st.spinner("The agents are working (this can take a minute)..."):
            st.session_state["result"] = asyncio.run(advisor.analyze(
                monthly_income=int(income), expenses=expenses, debts=debts,
                monthly_debt_budget=int(debt_budget), current_savings=int(savings_now)))
    except Exception as e:
        st.session_state.pop("result", None)
        st.error(f"Analysis failed: {type(e).__name__}")


# ------------------------------------------------------------------ results
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


res = st.session_state.get("result")
if res:
    st.divider()
    for w in res["warnings"]:
        st.warning(w)
    t1, t2, t3 = st.tabs(["📊 Budget", "🏦 Savings", "💳 Debt"])
    with t1:
        show_budget(res)
    with t2:
        show_savings(res)
    with t3:
        show_debt(res)

st.markdown(
    '<div class="disclaimer"><b>Please note.</b> This tool gives general information, not '
    "financial advice. AI output can contain mistakes, so check figures against your own records. "
    "Your numbers are sent to Groq to generate the advice, so don't enter names, account numbers "
    "or other personal identifiers.</div>",
    unsafe_allow_html=True)