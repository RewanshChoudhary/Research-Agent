"""
Prompt chunker — model-aware context configuration.

The original hard-coded MAX_CONTEXT_TOKENS=128000 which is only valid for
large-context models (e.g. llama-3.1-70b-128k).  The Compose default model
is `llama3-groq-8b-8192-tool-use-preview` which has an 8 192-token context.
Sending 128 k-sized prompts to an 8 k model causes the provider to either
truncate silently or raise an error — triggering the expensive 4-60 s tenacity
retry loop.

Set MAX_CONTEXT_TOKENS in .env to match your actual deployed model:
  - Groq llama3-8b-8192        →  8 192
  - Groq llama-3.3-70b-versatile → 128 000
  - NVIDIA NIM nemotron-70b    → 128 000
"""

import os

import structlog
import tiktoken


log = structlog.get_logger()

ENCODING_NAME = os.getenv("TOKENIZER_ENCODING", "cl100k_base")

# Default to a conservative 8 192 tokens to match the Groq default model.
# Override via MAX_CONTEXT_TOKENS= in .env for large-context models.
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "8192"))
RESERVED_OUTPUT_TOKENS = int(os.getenv("RESERVED_OUTPUT_TOKENS", "1024"))
CHUNK_OVERLAP_TOKENS = int(os.getenv("CHUNK_PROMPT_OVERLAP", "100"))

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
