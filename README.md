# AI Financial Coach

Multi-agent personal finance coach (RWF). Three LLM agents (budget, savings, debt) run in
sequence through Google ADK. All numbers are computed by tested Python code and the LLMs
only write advice, so figures are reliable.

## Run locally
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements-dev.txt
    copy .env.example .env      # then add your Groq key
    streamlit run app.py

## Test
    pytest -v
    python run_evals.py 2       # LLM eval harness, about 10 minutes on Groq's free tier

## Design notes
- Code computes totals, percentages, surplus and payoff plans; LLMs write only advice.
- Pydantic schemas validate every agent output; failures degrade gracefully with warnings.
- Evals run several times per scenario with deterministic checks.
- Bring-your-own-key: visitors supply their own Groq key.

Not financial advice.