from schemas import Debt

SCENARIOS = [
    {
        "name": "healthy_surplus",
        "inputs": dict(
            monthly_income=1_200_000,
            expenses={"Rent": 300_000, "Food": 150_000, "Transport": 80_000,
                      "Entertainment": 70_000, "Utilities": 50_000},
            debts=[Debt(name="Bank Loan", amount=1_000_000, interest_rate=14, min_payment=40_000)],
            monthly_debt_budget=150_000, current_savings=500_000),
    },
    {
        "name": "tight_budget",
        "inputs": dict(
            monthly_income=400_000,
            expenses={"Rent": 150_000, "Food": 120_000, "Transport": 60_000, "Airtime & Data": 40_000},
            debts=[Debt(name="SACCO Loan", amount=300_000, interest_rate=18, min_payment=15_000)],
            monthly_debt_budget=20_000, current_savings=0),
    },
    {
        "name": "deficit",
        "inputs": dict(
            monthly_income=300_000,
            expenses={"Rent": 180_000, "Food": 120_000, "Transport": 40_000},
            debts=[Debt(name="SACCO Loan", amount=200_000, interest_rate=18, min_payment=10_000)],
            monthly_debt_budget=10_000, current_savings=20_000),
    },
    {
        "name": "no_debts",
        "inputs": dict(
            monthly_income=900_000,
            expenses={"Rent": 250_000, "Food": 140_000, "Transport": 70_000, "Entertainment": 60_000},
            debts=[], monthly_debt_budget=0, current_savings=200_000),
    },
    {
        "name": "heavy_debt",
        "inputs": dict(
            monthly_income=600_000,
            expenses={"Rent": 200_000, "Food": 150_000, "Transport": 60_000},
            debts=[Debt(name="Credit Card", amount=800_000, interest_rate=36, min_payment=40_000),
                   Debt(name="Bank Loan", amount=2_500_000, interest_rate=14, min_payment=60_000)],
            monthly_debt_budget=150_000, current_savings=0),
    },
]