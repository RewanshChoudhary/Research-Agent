import os
from dataclasses import dataclass

import dotenv
import structlog
from openai import AsyncOpenAI, RateLimitError, APITimeoutError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


dotenv.load_dotenv()
log = structlog.get_logger()

BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

if not API_KEY:
    log.warning("llm_api_key_missing", expected="GROQ_API_KEY or LLM_API_KEY")

client = AsyncOpenAI(
    api_key=API_KEY or "missing-key",
    base_url=BASE_URL,
    timeout=None,
)

@dataclass
class LLMResponse:
    content: str
    total_tokens: int


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
)
async def llm_complete(
    prompt: str,
    system: str = "",
    model: str = "",
) -> LLMResponse:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        resp = await client.chat.completions.create(
            model=model or DEFAULT_MODEL,
            messages=messages,
            temperature=0.3,
        )
    except Exception:
        log.exception("llm request failed")
        raise

    return LLMResponse(
        content=resp.choices[0].message.content or "",
        total_tokens=resp.usage.total_tokens if resp.usage else 0,
    )
