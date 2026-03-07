"""Unit tests for history_tales_agent.utils.coerce."""

from __future__ import annotations

import pytest

from history_tales_agent.utils.coerce import coerce_to_str_list


class TestCoerceToStrList:
    """Verify coerce_to_str_list handles every format the LLM may return."""

    def test_plain_strings_pass_through(self):
        items = ["alpha", "bravo", "charlie"]
        assert coerce_to_str_list(items) == ["alpha", "bravo", "charlie"]

    def test_dicts_with_detail_key(self):
        items = [
            {"type": "CRITICAL", "detail": "Something is wrong"},
            {"type": "WARNING", "detail": "Could be better"},
        ]
        result = coerce_to_str_list(items)
        assert result == [
            "[CRITICAL] Something is wrong",
            "[WARNING] Could be better",
        ]

    def test_dicts_with_question_key(self):
        """open_loops format from outline node."""
        items = [
            {"type": "primary", "question": "Did they escape?", "opened_here": True},
            {"type": "secondary", "question": "Who helped?", "opened_here": False},
        ]
        result = coerce_to_str_list(items)
        assert result == [
            "[primary] Did they escape?",
            "[secondary] Who helped?",
        ]

    def test_dicts_with_message_key(self):
        items = [{"message": "Something happened"}]
        result = coerce_to_str_list(items)
        assert result == ["Something happened"]

    def test_dicts_with_text_key(self):
        items = [{"text": "A named entity"}]
        result = coerce_to_str_list(items)
        assert result == ["A named entity"]

    def test_dicts_with_recommendation_key(self):
        items = [{"recommendation": "Fix the ending"}]
        result = coerce_to_str_list(items)
        assert result == ["Fix the ending"]

    def test_dict_without_known_keys_falls_back_to_str(self):
        items = [{"foo": "bar", "baz": 42}]
        result = coerce_to_str_list(items)
        assert len(result) == 1
        assert "foo" in result[0]  # str(dict) representation

    def test_dict_with_type_but_no_text_keys(self):
        items = [{"type": "ISSUE", "unknown_key": "val"}]
        result = coerce_to_str_list(items)
        assert len(result) == 1
        assert "[ISSUE]" in result[0]

    def test_mixed_types(self):
        items = [
            "plain string",
            {"type": "ERR", "detail": "structured issue"},
            42,
            {"question": "open loop?"},
        ]
        result = coerce_to_str_list(items)
        assert result[0] == "plain string"
        assert result[1] == "[ERR] structured issue"
        assert result[2] == "42"
        assert result[3] == "open loop?"

    def test_empty_list(self):
        assert coerce_to_str_list([]) == []

    def test_no_label_key(self):
        """When label_key is None, no prefix is added."""
        items = [{"type": "ERR", "detail": "issue"}]
        result = coerce_to_str_list(items, label_key=None)
        assert result == ["issue"]

    def test_custom_text_keys(self):
        items = [{"custom": "value"}]
        result = coerce_to_str_list(items, text_keys=("custom",))
        assert result == ["value"]
