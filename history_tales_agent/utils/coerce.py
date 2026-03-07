"""Coercion helpers for normalising LLM output.

LLMs may return structured dicts where we expect plain strings.
These helpers convert flexibly so the pipeline never crashes on
schema mismatches.
"""

from __future__ import annotations

from typing import Any, Sequence


def coerce_to_str_list(
    items: Sequence[Any],
    *,
    text_keys: tuple[str, ...] = ("question", "detail", "message", "text", "recommendation"),
    label_key: str | None = "type",
) -> list[str]:
    """Convert a list that may contain dicts into a ``list[str]``.

    For each element:
    - **str** → kept as-is.
    - **dict** → first matching *text_key* is used as the main text.
      If *label_key* is provided and present, the result is
      ``"[LABEL] text"``.  Falls back to ``str(item)``.
    - **anything else** → ``str(item)``.
    """
    result: list[str] = []
    for item in items:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            # Find the best text value
            text = ""
            for key in text_keys:
                if key in item and item[key]:
                    text = str(item[key])
                    break
            if not text:
                text = str(item)

            # Optionally prefix with a label
            if label_key and label_key in item and item[label_key]:
                text = f"[{item[label_key]}] {text}"

            result.append(text)
        else:
            result.append(str(item))
    return result
