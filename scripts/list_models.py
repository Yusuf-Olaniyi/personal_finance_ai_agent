import os, httpx
from dotenv import load_dotenv

load_dotenv()
r = httpx.get(
    "https://api.groq.com/openai/v1/models",
    headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
)
r.raise_for_status()
for model_id in sorted(m["id"] for m in r.json()["data"]):
    print(model_id)