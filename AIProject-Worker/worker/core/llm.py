import os
from dataclasses import dataclass

import dotenv
import structlog
from openai import AsyncOpenAI, RateLimitError, APITimeoutError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from worker.core.prompt_chunker import count_tokens, chunk_content, fits_in_context, MAX_PROMPT_TOKENS


dotenv.load_dotenv()
log = structlog.get_logger()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

if LLM_PROVIDER == "groq":
    BASE_URL = "https://api.groq.com/openai/v1"
    API_KEY = os.getenv("GROQ_API_KEY")
    DEFAULT_MODEL = os.getenv("LLM_MODEL", "llama3-groq-8b-8192-tool-use-preview")
elif LLM_PROVIDER == "nvidia":
    BASE_URL = os.getenv("LLM_BASE_URL", "http://host.docker.internal:11434/v1")
    API_KEY = os.getenv("LLM_API_KEY") or os.getenv("WORKER_TOKEN", "default-key")
    DEFAULT_MODEL = os.getenv("LLM_MODEL", "llama3.1-nemotron-70b-instruct")
elif LLM_PROVIDER == "gemini":
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
    API_KEY = os.getenv("GEMINI_API_KEY")
    DEFAULT_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")
else:
    BASE_URL = "https://api.groq.com/openai/v1"
    API_KEY = os.getenv("GROQ_API_KEY")
    DEFAULT_MODEL = os.getenv("LLM_MODEL", "llama3-groq-8b-8192-tool-use-preview")
    log.warning("llm_unknown_provider", provider=LLM_PROVIDER)

LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60.0"))

if not API_KEY:
    key_map = {"groq": "GROQ_API_KEY", "nvidia": "LLM_API_KEY", "gemini": "GEMINI_API_KEY"}
    log.warning(
        "llm_api_key_missing",
        expected=key_map.get(LLM_PROVIDER, "GROQ_API_KEY or LLM_API_KEY or GEMINI_API_KEY"),
    )

client = AsyncOpenAI(
    api_key=API_KEY or "missing-key",
    base_url=BASE_URL,
    timeout=LLM_TIMEOUT,
)

@dataclass
class LLMResponse:
    content: str
    total_tokens: int


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
)
async def llm_complete(
    prompt: str,
    system: str = "",
    model: str = "",
) -> LLMResponse:
    prompt_tok = count_tokens(prompt)
    system_tok = count_tokens(system)
    total = prompt_tok + system_tok
    if total > MAX_PROMPT_TOKENS:
        log.warning(
            "prompt_exceeds_context_window",
            prompt_tokens=prompt_tok,
            system_tokens=system_tok,
            max_allowed=MAX_PROMPT_TOKENS,
        )
    else:
        log.debug("llm_call", prompt_tokens=prompt_tok, system_tokens=system_tok)

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

    if not resp.choices:
        raise RuntimeError(f"LLM returned empty choices (model={model or DEFAULT_MODEL})")
    return LLMResponse(
        content=resp.choices[0].message.content or "",
        total_tokens=resp.usage.total_tokens if resp.usage else 0,
    )


async def chunked_llm_complete(
    prompt: str,
    system: str = "",
    model: str = "",
) -> LLMResponse:
    if fits_in_context(prompt, system):
        return await llm_complete(prompt=prompt, system=system, model=model)

    system_tok = count_tokens(system)
    available = MAX_PROMPT_TOKENS - system_tok

    log.warning(
        "splitting_oversized_prompt",
        total_tokens=count_tokens(prompt) + system_tok,
        max_allowed=MAX_PROMPT_TOKENS,
        available_for_content=available,
    )

    chunks = chunk_content(prompt, max_tokens=available)

    results: list[LLMResponse] = []
    total_tok = 0
    for i, chunk in enumerate(chunks):
        log.info("chunked_llm_call", chunk_index=i, total_chunks=len(chunks))
        resp = await llm_complete(prompt=chunk, system=system, model=model)
        results.append(resp)
        total_tok += resp.total_tokens

    if len(results) == 1:
        return results[0]

    combined = "\n\n".join(r.content.strip() for r in results)
    return LLMResponse(content=combined, total_tokens=total_tok)
