from typing import Annotated, List, Optional
from pydantic import BaseModel, BeforeValidator, Field


def _to_rwf(value):
    """Coerce LLM-style money values (150000.0, '150,000', 'RWF 150000') to int."""
    if value is None or isinstance(value, int):
        return value
    if isinstance(value, str):
        cleaned = "".join(ch for ch in value if ch.isdigit() or ch in ".-")
        if cleaned in ("", ".", "-"):
            raise ValueError(f"Cannot parse money value: {value!r}")
        value = cleaned
    return round(float(value))


RWF = Annotated[int, BeforeValidator(_to_rwf), Field(ge=0)]
Percent = Annotated[float, Field(ge=0, le=100)]


# ---------- Budget agent ----------
class SpendingCategory(BaseModel):
    category: str
    amount: RWF
    percentage: Optional[Percent] = None


class SpendingRecommendation(BaseModel):
    category: str
    recommendation: str
    potential_savings: RWF = 0


class BudgetAnalysis(BaseModel):
    total_expenses: RWF
    monthly_income: Optional[RWF] = None
    spending_categories: List[SpendingCategory] = Field(default_factory=list)
    recommendations: List[SpendingRecommendation] = Field(default_factory=list)


# ---------- Savings agent ----------
class EmergencyFund(BaseModel):
    recommended_amount: RWF
    current_amount: RWF = 0
    current_status: str = ""


class SavingsRecommendation(BaseModel):
    goal: str            # where the money goes, e.g. "Emergency fund"
    amount: RWF
    rationale: str = ""


class AutomationTechnique(BaseModel):
    name: str
    description: str = ""
    monthly_amount: RWF = 0   # total RWF per month this automation moves


class SavingsStrategy(BaseModel):
    emergency_fund: EmergencyFund
    recommendations: List[SavingsRecommendation] = Field(default_factory=list)
    automation_techniques: List[AutomationTechnique] = Field(default_factory=list)


# ---------- Debt agent ----------
class Debt(BaseModel):
    name: str
    amount: RWF
    interest_rate: Percent          # annual percentage, e.g. 18 means 18%
    min_payment: RWF = 0


class PayoffPlan(BaseModel):
    total_interest: RWF
    months_to_payoff: int = Field(ge=0)
    monthly_payment: RWF
    order: List[str] = Field(default_factory=list)  # debt names, in payoff order


class PayoffPlans(BaseModel):
    avalanche: PayoffPlan
    snowball: PayoffPlan


class DebtRecommendation(BaseModel):
    title: str
    description: str = ""
    impact: str = ""


class DebtReduction(BaseModel):
    total_debt: RWF
    debts: List[Debt] = Field(default_factory=list)
    payoff_plans: PayoffPlans
    recommendations: List[DebtRecommendation] = Field(default_factory=list)


class BudgetAdvice(BaseModel):
    """What the budget LLM is allowed to produce: advice only, no totals."""
    recommendations: List[SpendingRecommendation] = Field(default_factory=list)


class DebtAdvice(BaseModel):
    """What the debt LLM is allowed to produce: advice only, no payoff math."""
    recommendations: List[DebtRecommendation] = Field(default_factory=list)