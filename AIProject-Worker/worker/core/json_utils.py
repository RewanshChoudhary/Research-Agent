"""Utilities for parsing JSON from LLM responses.

LLMs frequently wrap their JSON output in markdown code fences like:
    ```json
    { ... }
    ```
Direct json.loads() on such a response raises JSONDecodeError.
Use parse_json_from_llm() everywhere instead of json.loads(result.content).
"""

import json
import re


def strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` fences from an LLM response."""
    # Strip leading/trailing whitespace first
    text = text.strip()
    # Remove opening fence with optional language tag
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    # Remove closing fence
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_json_from_llm(content: str):
    """Parse JSON from an LLM response, stripping markdown fences if present.

    Raises json.JSONDecodeError if the content cannot be parsed even after cleaning.
    """
    cleaned = strip_markdown_fences(content)
    return json.loads(cleaned)
