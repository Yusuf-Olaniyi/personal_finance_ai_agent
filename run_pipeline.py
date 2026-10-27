import asyncio
from agents import FinanceAdvisor
from schemas import Debt


async def main():
    advisor = FinanceAdvisor()
    result = await advisor.analyze(
        monthly_income=800_000,
        expenses={"Rent": 250_000, "Food": 180_000, "Transport": 90_000,
                  "Airtime & Data": 30_000, "Entertainment": 60_000, "Utilities": 45_000},
        debts=[
            Debt(name="Bank Loan", amount=1_500_000, interest_rate=16, min_payment=50_000),
            Debt(name="SACCO Loan", amount=400_000, interest_rate=18, min_payment=20_000),
            Debt(name="Phone Installments", amount=150_000, interest_rate=0, min_payment=10_000),
        ],
        monthly_debt_budget=120_000,
        current_savings=100_000,
    )
    print("WARNINGS:", result["warnings"] or "none")
    for key in ("budget", "savings", "debt"):
        print(f"\n=== {key.upper()} ===")
        print(result[key].model_dump_json(indent=2) if result[key] else "None")


asyncio.run(main())