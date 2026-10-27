import asyncio, os, sys
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from finance_coach.agents.advisor import make_model

load_dotenv()

def check_config():
    if not os.getenv("GROQ_API_KEY"):
        sys.exit("FAIL: GROQ_API_KEY is not set (check your .env file)")

async def run_smoke():
    model = make_model()
    agent = LlmAgent(name="PingAgent", model=model,
                     instruction="Reply with one short friendly sentence.")
    svc = InMemorySessionService()
    await svc.create_session(app_name="smoke", user_id="u1", session_id="s1")
    runner = Runner(agent=agent, app_name="smoke", session_service=svc)

    msg = types.Content(role="user", parts=[types.Part(text="Say hello")])
    reply = None
    async for event in runner.run_async(user_id="u1", session_id="s1", new_message=msg):
        if event.error_message:
            raise RuntimeError(f"Model error: {event.error_message}")
        if event.is_final_response() and event.content and event.content.parts:
            reply = event.content.parts[0].text

    assert reply and reply.strip(), "Empty response"
    assert len(reply) < 200, f"Response too long, reasoning may be leaking: {reply[:80]}..."
    return reply

if __name__ == "__main__":
    check_config()
    try:
        reply = asyncio.run(asyncio.wait_for(run_smoke(), timeout=30))
        print(f"PASS: {reply}")
    except Exception as e:
        sys.exit(f"FAIL: {type(e).__name__}: {e}")