"""Central configuration: API keys, model names, the step ca
p, and an LLM factory."""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

# The supervisor routes constantly and only picks the next agent, so it runs on
# the cheap, low-latency lite model.
MODEL_SUPERVISOR: str = "gemini-3.1-flash-lite"

USE_HIGH_QUALITY_WORKER: bool = False
MODEL_WORKER: str = (
 "gemini-3.5-flash" if USE_HIGH_QUALITY_WORKER else "gemini-3.1-flash-lite"
)

# Hard cap on supervisor turns so it doesn't loop forever.
MAX_STEPS: int = 12

TAVILY_MAX_RESULTS: int = 5


def require_keys() -> None:
    """Fail fast with a clear message if either API key is missing.""" 

    if not GEMINI_API_KEY:
            raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and paste "
            "your key from https://aistudio.google.com/apikey"
        )
    if not TAVILY_API_KEY:
            raise RuntimeError(
                "TAVILY_API_KEY is not set. Copy .env.example to .env and paste "
                "your key from https://app.tavily.com"
            )


def make_llm(model: str, temperature: float = 0.3):
    """Build a Gemini chat model. Lower temperature for routing, higher for prose."""

    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=GEMINI_API_KEY,
        temperature=temperature,
    )

