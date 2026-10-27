import os

from dotenv import load_dotenv

load_dotenv()  # finds .env by walking up from this file to the project root

APP_NAME = "finance_coach"
USER_ID = "local_user"
DEFAULT_MODEL = "groq/openai/gpt-oss-120b"


def model_name() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_MODEL)