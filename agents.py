import json
import os
import uuid
from typing import Dict, List, Optional

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from openai import api_key
from pydantic import BaseModel, ValidationError

from facts import compute_facts
from payoff import build_payoff_plans
from schemas import (
    BudgetAdvice, BudgetAnalysis, Debt, DebtAdvice, DebtReduction,
    EmergencyFund, SavingsStrategy, SpendingCategory,
)

load_dotenv()
APP_NAME = "finance_coach"
USER_ID = "local_user"


def make_model(api_key: Optional[str] = None):
    kwargs = dict(
        model=os.getenv("LLM_MODEL", "groq/openai/gpt-oss-120b"),
        reasoning_effort="low",
        include_reasoning=False,
        temperature=0.2,
        num_retries=4,
    )
    if api_key:
        kwargs["api_key"] = api_key
    return LiteLlm(**kwargs)


# NOTE: ADK treats {name} in an instruction as a placeholder filled from
# session state. So these prompts must contain NO other curly braces.

BUDGET_INSTRUCTION = """You are a Budget Analysis Agent. All amounts are in Rwandan francs (RWF).
Verified facts about the user's finances (computed by code, never recalculate them):
{facts}

Give 3 to 5 specific recommendations for reducing spending.
Rules:
- Each recommendation's category must be copied exactly from the spending categories in the facts. Never use a debt or loan as a category.
- Use each category at most once.
- potential_savings is whole RWF per month and must be realistic: at most 25 percent of that category's amount.
- Do not mention other agents.
- If surplus is negative, prioritise closing that deficit.
Respond only with JSON matching the required schema."""

SAVINGS_INSTRUCTION = """You are a Savings Strategy Agent. All amounts are in Rwandan francs (RWF).
Verified facts:
{facts}

Budget advice already given (do not repeat it):
{budget_advice}

The only money you may allocate is surplus_after_debt from the facts, per month. Savings from the budget advice are a bonus the user may add later, so do not count them.

Rules:
- Each recommendation is a goal, meaning a place the money goes (for example Emergency fund, SACCO savings, Education fund), never a spending category. amount is whole RWF per month.
- The recommended amounts must add up to at most surplus_after_debt. Never allocate money to debt repayment.
- If surplus_after_debt is zero or negative, return an empty recommendations list and an empty automation_techniques list, and use current_status to explain in one or two sentences that there is nothing to save yet and what to focus on.
- Otherwise give 1 to 3 automation techniques (for example a mobile money standing order or a SACCO contribution). Each has a monthly_amount, the total RWF per month it moves. Their monthly_amounts must add up to at most the total of your recommended amounts.
- Do not create separate savings accounts per spending category. Do not mention other agents.
Respond only with JSON matching the required schema."""

DEBT_INSTRUCTION = """You are a Debt Reduction Agent. All amounts are in Rwandan francs (RWF).
Verified facts:
{facts}

Payoff plans already calculated by code:
{payoff_plans}

Rules:
- The user pays exactly monthly_payment per month toward debt, as in the plans. Never suggest a different payment amount and never suggest lowering minimum payments.
- Quote months, interest and payments only as given in the plans. Do not state when an individual debt will be cleared and do not invent any other figures.
- Do not discuss savings, the emergency fund, spending cuts or the user's surplus. Other parts of the app handle those. Do not mention other agents.

Compare avalanche and snowball and recommend one with reasons. If the two plans are identical, say so and explain why (only one debt, or one debt has both the highest interest rate and the smallest balance). Give 3 to 4 concrete recommendations about the debt itself (for example automating payments, avoiding new borrowing, negotiating a lower interest rate, checking for early repayment fees), each with a title, a description and the expected impact. If there are no debts, congratulate the user and suggest how to stay debt-free.
Respond only with JSON matching the required schema."""

def _coerce(value, model: type[BaseModel]) -> Optional[BaseModel]:
    """Validate whatever ADK stored (dict or JSON string); None if unusable."""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            return model.model_validate_json(value)
        return model.model_validate(value)
    except ValidationError:
        return None

def _friendly(msg: str) -> str:
    low = msg.lower()
    if "ratelimit" in low or "rate limit" in low:
        return "The AI provider's rate limit was reached. Wait about a minute and try again."
    if "json_validate_failed" in low:
        return "The model returned malformed output for one step."
    if "authentication" in low or "invalid api key" in low or "401" in low:
        return "The API key was rejected. Check that you pasted a valid Groq key."
    return f"Unexpected error: {msg[:200]}"


class FinanceAdvisor:
    def __init__(self, api_key: Optional[str] = None):
        model = make_model(api_key)
        self.session_service = InMemorySessionService()

        budget = LlmAgent(
            name="BudgetAnalysisAgent", model=model,
            description="Recommends ways to reduce spending.",
            instruction=BUDGET_INSTRUCTION,
            output_schema=BudgetAdvice, output_key="budget_advice",
        )
        savings = LlmAgent(
            name="SavingsStrategyAgent", model=model,
            description="Builds a savings and emergency fund plan.",
            instruction=SAVINGS_INSTRUCTION,
            output_schema=SavingsStrategy, output_key="savings_strategy",
        )
        debt = LlmAgent(
            name="DebtReductionAgent", model=model,
            description="Explains and recommends a debt payoff strategy.",
            instruction=DEBT_INSTRUCTION,
            output_schema=DebtAdvice, output_key="debt_advice",
        )
        self.pipeline = SequentialAgent(
            name="FinanceCoordinatorAgent",
            description="Runs budget, savings and debt agents in order.",
            sub_agents=[budget, savings, debt],
        )
        self.runner = Runner(
            agent=self.pipeline, app_name=APP_NAME,
            session_service=self.session_service,
        )

    async def analyze(
        self,
        monthly_income: int,
        expenses: Dict[str, int],
        debts: List[Debt],
        monthly_debt_budget: int,
        current_savings: int = 0,
    ) -> dict:
        warnings: List[str] = []
        facts = compute_facts(monthly_income, expenses, debts, monthly_debt_budget, current_savings)

        plans = None
        if debts:
            try:
                plans = build_payoff_plans(debts, monthly_debt_budget)
            except ValueError as e:
                warnings.append(f"Debt plan unavailable: {e}")

        session_id = f"finance_{uuid.uuid4().hex[:8]}"
        await self.session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
            state={
                "facts": json.dumps(facts),
                "payoff_plans": plans.model_dump_json() if plans else "No payoff plan available.",
            },
        )

        msg = types.Content(role="user", parts=[types.Part(
            text="Analyze my finances using the verified facts provided.")])
        try:
            async for event in self.runner.run_async(
                user_id=USER_ID, session_id=session_id, new_message=msg
            ):
                if event.error_message:
                    warnings.append(f"Model error: {event.error_message}")
        except Exception as e:
            warnings.append(f"Agent pipeline failed: {type(e).__name__}: {e}")

        session = await self.session_service.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
        state = session.state if session else {}
        await self.session_service.delete_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id)

        # ---- assemble final results: code owns the numbers ----
        b = _coerce(state.get("budget_advice"), BudgetAdvice)
        if b is None:
            warnings.append("Budget advice was missing or invalid.")
        budget = BudgetAnalysis(
            total_expenses=facts["total_expenses"],
            monthly_income=monthly_income,
            spending_categories=[SpendingCategory(**c) for c in facts["categories"]],
            recommendations=b.recommendations if b else [],
        )

        s = _coerce(state.get("savings_strategy"), SavingsStrategy)
        if s is None:
            warnings.append("Savings strategy was missing or invalid.")
        savings = SavingsStrategy(
            emergency_fund=EmergencyFund(
                recommended_amount=facts["emergency_fund_target"],
                current_amount=current_savings,
                current_status=s.emergency_fund.current_status if s else "",
            ),
            recommendations=s.recommendations if s else [],
            automation_techniques=s.automation_techniques if s else [],
        )

        d = _coerce(state.get("debt_advice"), DebtAdvice)
        if debts and d is None:
            warnings.append("Debt advice was missing or invalid.")
        debt_result = (
            DebtReduction(
                total_debt=facts["total_debt"], debts=debts, payoff_plans=plans,
                recommendations=d.recommendations if d else [],
            ) if plans else None
        )

        return {"budget": budget, "savings": savings, "debt": debt_result,
                "facts": facts, "warnings": warnings}