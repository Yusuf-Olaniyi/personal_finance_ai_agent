import asyncio
import os
from pathlib import Path
import logging

import pandas as pd
import streamlit as st

from finance_coach.agents.advisor import FinanceAdvisor
from finance_coach.config import model_name
from finance_coach.data.csv_parser import CSVError, parse_expense_csv
from finance_coach.data.inputs import DEBT_COLS, df_to_debts, df_to_expenses
from finance_coach.ui.results import rwf, show_budget, show_debt, show_savings
from finance_coach.ui.theme import inject_css
from finance_coach.config import MAX_CATEGORIES, MAX_DEBTS, model_name
from finance_coach.guard import UsageGuard

ASSETS = Path(__file__).parent / "assets"

st.set_page_config(page_title="AI Financial Coach", page_icon="💰", layout="wide")
inject_css()

# ------------------------------------------------------------------ sidebar
@st.cache_resource
def get_guard() -> UsageGuard:
    # cache_resource is shared by all visitors in the server process
    return UsageGuard(
        daily_cap=int(os.getenv("DEMO_DAILY_CAP", "100")),
        cooldown_s=int(os.getenv("DEMO_COOLDOWN_SECONDS", "30")),
    )


api_key = os.getenv("GROQ_API_KEY")  # server-side only; never displayed
# TEMPORARY DEBUG: remove after fixing
st.sidebar.caption(f"debug: GROQ vars = {[repr(k) for k in os.environ if 'GROQ' in k.upper()]}, "
                   f"key length = {len(api_key or '')}")
with st.sidebar:
    st.markdown("### ℹ️ About this demo")
    st.caption("A free demo on a shared AI quota. Analyses run one at a time "
               "and a daily limit applies, so if it's busy, try again in a minute.")
    st.caption(f"Model: {model_name()}")
    st.divider()
    st.markdown("### 📄 CSV template")
    st.markdown("Columns: **Date**, **Category**, **Amount**. Several months are fine.")
    st.download_button("Download sample CSV", (ASSETS / "sample_expenses.csv").read_bytes(),
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
    problems.append("This demo is not configured yet: the server has no AI key.")
if len(expenses) > MAX_CATEGORIES:
    problems.append(f"Please use at most {MAX_CATEGORIES} expense categories.")
if len(debts) > MAX_DEBTS:
    problems.append(f"Please enter at most {MAX_DEBTS} debts.")
if any(len(c) > 60 for c in expenses):
    problems.append("Category names must be 60 characters or fewer.")

for p in problems:
    st.warning(p)

# ----------------------------------------------------------------- analysis
if st.button("Analyse my finances", type="primary", disabled=bool(problems)):
    guard = get_guard()
    ok, message = guard.try_start()
    if not ok:
        st.warning(message)
    else:
        try:
            advisor = FinanceAdvisor(api_key=api_key)  # fresh per run: avoids closed-event-loop issues
            with st.spinner("The agents are working (this can take a minute)..."):
                st.session_state["result"] = asyncio.run(advisor.analyze(
                    monthly_income=int(income), expenses=expenses, debts=debts,
                    monthly_debt_budget=int(debt_budget), current_savings=int(savings_now)))
        except Exception as e:
            logging.exception("Analysis failed")
            st.session_state.pop("result", None)
            st.error(f"Analysis failed ({type(e).__name__}). Please try again.")
        finally:
            guard.finish()   # always release the slot, even on errors

# ------------------------------------------------------------------ results
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