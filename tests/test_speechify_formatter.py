"""Tests for the Speechify TTS formatter."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest

from history_tales_agent.output.speechify_formatter import (
    _enforce_paragraph_length,
    _enforce_sentence_length,
    _split_long_sentence,
    _strip_speechify_artifacts,
    format_speechify,
    validate_speechify_word_count,
    write_speechify_script,
)


# ─── Artifact stripping ─────────────────────────────────────


class TestSpeechifyStripping:
    """All TTS and formatting artifacts must be removed."""

    def test_audio_tags_stripped(self):
        text = "[curious] The door creaked open."
        result = _strip_speechify_artifacts(text)
        assert "[curious]" not in result
        assert "The door creaked open." in result

    def test_all_audio_tag_variants(self):
        tags = ["[tense]", "[solemn]", "[resolve]", "[sensory]",
                "[whispered]", "[climax]", "[revelation]"]
        for tag in tags:
            text = f"{tag} Some narration here."
            result = _strip_speechify_artifacts(text)
            assert tag not in result, f"{tag} was not stripped"
            assert "Some narration here." in result

    def test_ssml_breaks_stripped(self):
        text = 'Pause here. <break time="1.5s" /> Continue speaking.'
        result = _strip_speechify_artifacts(text)
        assert "<break" not in result
        assert "Pause here." in result
        assert "Continue speaking." in result

    def test_ssml_break_variants(self):
        text = '<break time="0.3s" /> Hello. <break time="2.0s"/> World.'
        result = _strip_speechify_artifacts(text)
        assert "<break" not in result
        assert "Hello." in result
        assert "World." in result

    def test_ellipses_stripped(self):
        text = "He waited... and then it happened."
        result = _strip_speechify_artifacts(text)
        assert "..." not in result

    def test_unicode_ellipsis_stripped(self):
        text = "He waited\u2026 and then it happened."
        result = _strip_speechify_artifacts(text)
        assert "\u2026" not in result

    def test_em_dash_replaced_with_comma(self):
        text = "The soldier — a young man — stepped forward."
        result = _strip_speechify_artifacts(text)
        assert "—" not in result
        assert "soldier" in result
        assert "stepped forward" in result

    def test_en_dash_replaced(self):
        text = "The soldier \u2013 a young man \u2013 stepped forward."
        result = _strip_speechify_artifacts(text)
        assert "\u2013" not in result

    def test_bracket_notes_stripped(self):
        text = "The claim [C001] was verified."
        result = _strip_speechify_artifacts(text)
        assert "[C001]" not in result
        assert "was verified" in result

    def test_bracket_beat_stripped(self):
        text = "He spoke [pause] then continued."
        result = _strip_speechify_artifacts(text)
        assert "[pause]" not in result

    def test_caps_emphasis_lowered(self):
        text = "risk EVERYTHING for the cause."
        result = _strip_speechify_artifacts(text)
        assert "EVERYTHING" not in result
        assert "Everything" in result

    def test_known_acronyms_preserved(self):
        text = "The CIA and FBI collaborated with NATO."
        result = _strip_speechify_artifacts(text)
        assert "CIA" in result
        assert "FBI" in result
        assert "NATO" in result

    def test_markdown_bold_stripped(self):
        text = "This is **very important** text."
        result = _strip_speechify_artifacts(text)
        assert "**" not in result
        assert "very important" in result

    def test_markdown_italic_stripped(self):
        text = "This is *emphasized* text."
        result = _strip_speechify_artifacts(text)
        assert result.count("*") == 0
        assert "emphasized" in result

    def test_markdown_heading_stripped(self):
        text = "## Section Title\n\nBody text here."
        result = _strip_speechify_artifacts(text)
        assert "##" not in result
        assert "Section Title" in result
        assert "Body text here." in result

    def test_smart_quotes_converted(self):
        text = "\u201cHello,\u201d he said. \u2018World.\u2019"
        result = _strip_speechify_artifacts(text)
        assert "\u201c" not in result
        assert "\u201d" not in result
        assert "\u2018" not in result
        assert "\u2019" not in result
        assert '"Hello,"' in result

    def test_double_commas_cleaned(self):
        # Em dash at sentence boundary can produce ",,"
        text = "word, , next word."
        result = _strip_speechify_artifacts(text)
        assert ",," not in result
        assert ", ," not in result

    def test_multiple_spaces_collapsed(self):
        text = "word   word    word."
        result = _strip_speechify_artifacts(text)
        assert "   " not in result
        assert "    " not in result


# ─── Sentence-length enforcement ─────────────────────────────


class TestSentenceLength:
    """Sentences must be split when they exceed 25 words."""

    def test_short_sentence_unchanged(self):
        text = "The soldier walked across the field."
        result = _enforce_sentence_length(text)
        assert result.strip() == text

    def test_long_sentence_split(self):
        # Build a sentence with >25 words and a natural comma+conjunction
        text = (
            "The soldier walked across the muddy field and saw the bridge ahead, "
            "but the enemy had already positioned their guns on the far bank of the river."
        )
        result = _enforce_sentence_length(text)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", result) if s.strip()]
        # Should be split into at least 2 sentences
        assert len(sentences) >= 2
        for sent in sentences:
            assert len(sent.split()) <= 30  # Allow some tolerance from split mechanics

    def test_sentence_under_limit_not_split(self):
        text = "He ran. She walked. They waited."
        result = _enforce_sentence_length(text)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", result) if s.strip()]
        assert len(sentences) == 3

    def test_split_long_sentence_helper(self):
        sentence = (
            "The commander ordered the troops to advance across the wide open muddy field "
            "under heavy morning rain, but the enemy fire coming from the ridge was far too "
            "intense for them to continue safely."
        )
        parts = _split_long_sentence(sentence)
        assert len(parts) >= 2


# ─── Paragraph-length enforcement ────────────────────────────


class TestParagraphLength:
    """Paragraphs must have at most 2 sentences."""

    def test_short_paragraph_unchanged(self):
        text = "First sentence. Second sentence."
        result = _enforce_paragraph_length(text)
        assert result.strip() == text

    def test_long_paragraph_split(self):
        text = "Sentence one. Sentence two. Sentence three. Sentence four."
        result = _enforce_paragraph_length(text)
        paragraphs = [p.strip() for p in result.split("\n\n") if p.strip()]
        assert len(paragraphs) == 2
        for para in paragraphs:
            sentence_count = len([s for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()])
            assert sentence_count <= 2

    def test_single_sentence_paragraph(self):
        text = "Just one sentence."
        result = _enforce_paragraph_length(text)
        assert result.strip() == text

    def test_five_sentences_becomes_three_paragraphs(self):
        text = "One. Two. Three. Four. Five."
        result = _enforce_paragraph_length(text)
        paragraphs = [p.strip() for p in result.split("\n\n") if p.strip()]
        assert len(paragraphs) == 3  # 2 + 2 + 1

    def test_empty_paragraphs_removed(self):
        text = "One.\n\n\n\nTwo."
        result = _enforce_paragraph_length(text)
        paragraphs = [p.strip() for p in result.split("\n\n") if p.strip()]
        assert len(paragraphs) == 2


# ─── Word-count validation ──────────────────────────────────


class TestWordCountValidation:
    """Word count must be within ±3% of 115-WPM target."""

    def test_in_range(self):
        # 10 min → 1150 words; ±3% → 1115–1184
        text = " ".join(["word"] * 1150)
        result = validate_speechify_word_count(text, 10)
        assert result["in_range"] is True
        assert result["target"] == 1150
        assert result["word_count"] == 1150
        assert result["deviation_pct"] == 0.0

    def test_below_range(self):
        # 10 min → 1150 target; min = 1115; 1000 is below
        text = " ".join(["word"] * 1000)
        result = validate_speechify_word_count(text, 10)
        assert result["in_range"] is False
        assert result["word_count"] == 1000

    def test_above_range(self):
        # 10 min → 1150 target; max = 1184; 1300 is above
        text = " ".join(["word"] * 1300)
        result = validate_speechify_word_count(text, 10)
        assert result["in_range"] is False
        assert result["word_count"] == 1300

    def test_at_lower_boundary(self):
        # 10 min → 1150 * 0.97 = 1115.5 → int 1115
        text = " ".join(["word"] * 1116)
        result = validate_speechify_word_count(text, 10)
        assert result["in_range"] is True

    def test_at_upper_boundary(self):
        # 10 min → 1150 * 1.03 = 1184.5 → int 1184
        text = " ".join(["word"] * 1184)
        result = validate_speechify_word_count(text, 10)
        assert result["in_range"] is True

    def test_zero_length_video(self):
        text = ""
        result = validate_speechify_word_count(text, 0)
        assert result["target"] == 0
        assert result["deviation_pct"] == 0.0


# ─── Full pipeline (format_speechify) ────────────────────────


class TestFormatSpeechify:
    """Integration tests for the full Speechify pipeline."""

    def test_clean_output_no_artifacts(self):
        script = (
            "# The Great Escape\n\n"
            '--- [Opening (0–20s)] ---\n\n'
            "[curious] The tunnel stretched for three hundred feet.\n\n"
            "Re-hook: Would they make it?\n\n"
            "**Bold text** and *italic text* and [C001] trace tags.\n\n"
            'He waited... <break time="1.5s" /> and then he moved.\n\n'
            "The soldier — a decorated officer — ran EVERYTHING.\n\n"
            "This documentary script is a historical synthesis based on cited sources."
        )
        result = format_speechify(script)

        # Nothing that shouldn't be there
        assert "# " not in result
        assert "---" not in result
        assert "[curious]" not in result
        assert "Re-hook" not in result
        assert "**" not in result
        assert "[C001]" not in result
        assert "..." not in result
        assert "<break" not in result
        assert "—" not in result
        assert "EVERYTHING" not in result
        assert "historical synthesis" not in result

        # Core narration preserved
        assert "tunnel" in result
        assert "soldier" in result

    def test_output_is_plain_text(self):
        script = "Simple narration. Clean and clear."
        result = format_speechify(script)
        # No HTML, no markdown, no brackets
        assert "<" not in result
        assert ">" not in result
        assert "[" not in result
        assert "]" not in result
        assert "#" not in result
        assert "**" not in result

    def test_paragraphs_max_two_sentences(self):
        script = "One. Two. Three. Four. Five. Six."
        result = format_speechify(script)
        paragraphs = [p.strip() for p in result.split("\n\n") if p.strip()]
        for para in paragraphs:
            sentence_count = len([s for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()])
            assert sentence_count <= 2, f"Paragraph has {sentence_count} sentences: {para!r}"

    def test_ends_with_newline(self):
        script = "Hello world."
        result = format_speechify(script)
        assert result.endswith("\n")

    def test_no_excessive_blank_lines(self):
        script = "Line one.\n\n\n\n\nLine two."
        result = format_speechify(script)
        assert "\n\n\n" not in result


# ─── File writer ─────────────────────────────────────────────


class TestWriteSpeechifyScript:
    """Test the file-writing function."""

    def test_writes_file(self):
        state = {
            "final_script": "The tunnel stretched for three hundred feet. The air was cold.",
            "chosen_topic": None,
            "video_length_minutes": 1,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_speechify_script(state, tmpdir)
            assert path.exists()
            assert path.name == "script_speechify.txt"
            content = path.read_text(encoding="utf-8")
            assert "tunnel" in content
            assert len(content) > 0

    def test_empty_script_returns_path(self):
        state = {"final_script": "", "chosen_topic": None, "video_length_minutes": 1}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_speechify_script(state, tmpdir)
            assert path == Path(tmpdir) / "script_speechify.txt"
            assert not path.exists()  # file not written when empty

    def test_output_dir_created(self):
        state = {
            "final_script": "Some text here.",
            "chosen_topic": None,
            "video_length_minutes": 1,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = str(Path(tmpdir) / "sub" / "dir")
            path = write_speechify_script(state, nested)
            assert path.exists()

    def test_output_is_clean_plain_text(self):
        script = (
            "# Title\n\n"
            '--- [Act I] ---\n\n'
            "[tense] He ran **fast** through the night... and never looked back.\n\n"
            '<break time="1.0s" />\n\n'
            "The CIA tracked his movements."
        )
        state = {
            "final_script": script,
            "chosen_topic": None,
            "video_length_minutes": 1,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_speechify_script(state, tmpdir)
            content = path.read_text(encoding="utf-8")

            assert "# " not in content
            assert "---" not in content
            assert "[tense]" not in content
            assert "**" not in content
            assert "..." not in content
            assert "<break" not in content
            assert "CIA" in content  # acronym preserved
