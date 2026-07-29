import os

import structlog
import tiktoken


log = structlog.get_logger()

ENCODING_NAME = os.getenv("TOKENIZER_ENCODING", "cl100k_base")
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "128000"))
RESERVED_OUTPUT_TOKENS = int(os.getenv("RESERVED_OUTPUT_TOKENS", "4000"))
CHUNK_OVERLAP_TOKENS = int(os.getenv("CHUNK_PROMPT_OVERLAP", "200"))

MAX_PROMPT_TOKENS = MAX_CONTEXT_TOKENS - RESERVED_OUTPUT_TOKENS

_encoding = None


def _get_encoding():
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding(ENCODING_NAME)
    return _encoding


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_get_encoding().encode(text))


def chunk_content(
    content: str,
    max_tokens: int = MAX_PROMPT_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> list[str]:
    if not content:
        return []
    tokens = _get_encoding().encode(content)
    if len(tokens) <= max_tokens:
        return [content]
    log.warning(
        "chunking_content",
        total_tokens=len(tokens),
        max_tokens=max_tokens,
        num_chunks=(len(tokens) + max_tokens - 1) // max_tokens,
    )
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_text = _get_encoding().decode(tokens[start:end])
        chunks.append(chunk_text)
        start += max_tokens - overlap_tokens
    return chunks


def total_prompt_tokens(prompt: str, system: str = "") -> int:
    return count_tokens(system) + count_tokens(prompt)


def fits_in_context(prompt: str, system: str = "") -> bool:
    return total_prompt_tokens(prompt, system) <= MAX_PROMPT_TOKENS
