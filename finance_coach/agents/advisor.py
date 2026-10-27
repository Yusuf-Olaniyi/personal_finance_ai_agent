import json
import uuid
from typing import Dict, List, Optional

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, ValidationError

from finance_coach.agents.prompts import BUDGET_INSTRUCTION, DEBT_INSTRUCTION, SAVINGS_INSTRUCTION
from finance_coach.config import APP_NAME, USER_ID, model_name
from finance_coach.core.facts import compute_facts
from finance_coach.core.payoff import build_payoff_plans
from finance_coach.schemas import (
    BudgetAdvice, BudgetAnalysis, Debt, DebtAdvice, DebtReduction,
    EmergencyFund, SavingsStrategy, SpendingCategory,
)


def make_model(api_key: Optional[str] = None):
    kwargs = dict(
        model=model_name(),
        reasoning_effort="low",
        include_reasoning=False,
        temperature=0.2,
        num_retries=4,
    )
    if api_key:
        kwargs["api_key"] = api_key
    return LiteLlm(**kwargs)

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