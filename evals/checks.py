import re
from typing import List, NamedTuple

CHECK_NAMES = [
    "pipeline_clean", "has_budget_advice", "has_savings_advice", "has_debt_advice",
    "categories_known", "savings_within_category", "total_savings_sane",
    "allocation_within_surplus", "automation_within_allocation",
    "no_filler_when_no_surplus", "currency_is_rwf", "debt_presence_correct",
    "debt_names_strategy", "no_agent_names",
]

_AGENT_WORDS = re.compile(r"\bagents?\b|\w+agent\b", re.IGNORECASE)
_NUM = re.compile(r"\d{1,3}(?:,\d{3})+|\d{4,}")


class Check(NamedTuple):
    name: str
    passed: bool
    detail: str = ""


def _advice_text(result: dict) -> str:
    parts = []
    for r in result["budget"].recommendations:
        parts += [r.category, r.recommendation]
    s = result["savings"]
    parts.append(s.emergency_fund.current_status)
    for r in s.recommendations:
        parts += [r.goal, r.rationale]
    for t in s.automation_techniques:
        parts += [t.name, t.description]
    if result["debt"]:
        for r in result["debt"].recommendations:
            parts += [r.title, r.description, r.impact]
    return " ".join(parts)


def run_checks(result: dict) -> List[Check]:
    facts = result["facts"]
    budget, savings, debt = result["budget"], result["savings"], result["debt"]
    known = {c["category"].strip().lower(): c["amount"] for c in facts["categories"]}
    has_debts = bool(facts["debts"])
    text = _advice_text(result)
    allocated = sum(r.amount for r in savings.recommendations)
    automated = sum(t.monthly_amount for t in savings.automation_techniques)
    limit = max(facts["surplus_after_debt"], 0)
    out: List[Check] = []

    def add(name, passed, detail=""):
        out.append(Check(name, bool(passed), "" if passed else detail))

    add("pipeline_clean", not result["warnings"], "; ".join(result["warnings"]))
    add("has_budget_advice", len(budget.recommendations) >= 1, "no budget recommendations")
    add("has_savings_advice", limit <= 0 or len(savings.recommendations) >= 1,
        "there is a surplus but no savings recommendations")
    add("has_debt_advice",
        (not has_debts) or (debt is not None and len(debt.recommendations) >= 1),
        "user has debts but no debt recommendations")

    unknown = [r.category for r in budget.recommendations
               if r.category.strip().lower() not in known]
    add("categories_known", not unknown, f"categories not in the user's data: {unknown}")

    too_big = []
    for r in budget.recommendations:
        key = r.category.strip().lower()
        if key in known and r.potential_savings > known[key]:
            too_big.append(f"{r.category}: saving {r.potential_savings:,} > spend {known[key]:,}")
    add("savings_within_category", not too_big, "; ".join(too_big))

    total_saving = sum(r.potential_savings for r in budget.recommendations)
    add("total_savings_sane", total_saving <= facts["total_expenses"],
        f"claimed savings {total_saving:,} exceed total expenses {facts['total_expenses']:,}")

    add("allocation_within_surplus", allocated <= limit + 1,
        f"allocated {allocated:,} but surplus after debt payments is {limit:,}")

    no_amount = [t.name for t in savings.automation_techniques if t.monthly_amount <= 0]
    add("automation_within_allocation", automated <= allocated + 1 and not no_amount,
        f"automation moves {automated:,}/month vs {allocated:,} allocated; "
        f"techniques without an amount: {no_amount}")

    if limit > 0:
        add("no_filler_when_no_surplus", True)
    else:
        add("no_filler_when_no_surplus", not savings.recommendations and automated == 0,
            "savings advice allocates money although there is no surplus")

    m = re.search(r"[$€£]|\b(USD|EUR|GBP|dollars?)\b", text, re.IGNORECASE)
    add("currency_is_rwf", m is None, f"foreign currency mentioned: {m.group(0) if m else ''}")

    add("debt_presence_correct", (debt is not None) == has_debts,
        f"user has debts={has_debts} but debt result present={debt is not None}")

    if debt is None or len(facts["debts"]) < 2:
        add("debt_names_strategy", True)   # not applicable
    else:
        dtext = " ".join(f"{r.title} {r.description} {r.impact}" for r in debt.recommendations).lower()
        add("debt_names_strategy", "avalanche" in dtext or "snowball" in dtext,
            "debt advice never mentions avalanche or snowball")

    names = _AGENT_WORDS.search(text)
    add("no_agent_names", names is None, f"advice mentions: {names.group(0) if names else ''}")
    return out


# ---------------- soft signal: amounts in the advice with no source ----------------
def _walk_numbers(x, out: set):
    if isinstance(x, bool):
        return
    if isinstance(x, (int, float)):
        out.add(round(x))
    elif isinstance(x, dict):
        for v in x.values():
            _walk_numbers(v, out)
    elif isinstance(x, (list, tuple)):
        for v in x:
            _walk_numbers(v, out)


def ungrounded_numbers(result: dict) -> List[int]:
    """Money-sized numbers in the advice that are not in the facts, the payoff plans,
    or the agents' own structured amounts. A review list, not a verdict."""
    facts, budget, savings, debt = result["facts"], result["budget"], result["savings"], result["debt"]
    allowed: set = set()
    _walk_numbers(facts, allowed)
    if debt:
        _walk_numbers(debt.payoff_plans.model_dump(), allowed)
    allowed |= {r.potential_savings for r in budget.recommendations}
    allowed.add(sum(r.potential_savings for r in budget.recommendations))
    allowed |= {r.amount for r in savings.recommendations}
    allowed.add(sum(r.amount for r in savings.recommendations))
    allowed |= {t.monthly_amount for t in savings.automation_techniques}
    allowed.add(facts.get("emergency_fund_target", 0) - facts.get("current_savings", 0))
    found = {int(n.replace(",", "")) for n in _NUM.findall(_advice_text(result))}
    return sorted(found - allowed)