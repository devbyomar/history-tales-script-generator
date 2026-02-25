"""Tests for the ElevenLabs TTS formatter."""

from __future__ import annotations

import re

import pytest

from history_tales_agent.output.elevenlabs_formatter import (
    _apply_emphasis,
    _apply_pacing,
    _classify_sentence,
    _deduplicate_hedges,
    _extract_first_sentence,
    _normalise_for_tts,
    _treat_dialogue,
    format_elevenlabs,
)


# ─── Stripping ───────────────────────────────────────────────


class TestStripping:
    """Structural markers must be completely removed."""

    def test_section_headers_stripped(self):
        text = '--- [Opening (0–20s)] ---\n\nHello world.'
        result = format_elevenlabs(text)
        assert "---" not in result
        assert "Opening" not in result
        assert "Hello world." in result

    def test_md_title_stripped(self):
        text = "# Some Title\n\nBody text."
        result = format_elevenlabs(text)
        assert "# Some Title" not in result
        assert "Body text." in result

    def test_rehook_stripped(self):
        text = "Some text.\n\nRe-hook: The door closes.\n\nMore text."
        result = format_elevenlabs(text)
        assert "Re-hook" not in result
        assert "Some text." in result
        assert "More text." in result

    def test_crosscut_label_stripped_content_kept(self):
        text = "Cross-cut: The German officer read the intercept."
        result = format_elevenlabs(text)
        assert "Cross-cut:" not in result
        assert "The German officer read the intercept." in result

    def test_pivot_label_stripped(self):
        text = "Pivot: Armies moved on fuel."
        result = format_elevenlabs(text)
        assert "Pivot:" not in result
        assert "Armies moved on fuel." in result

    def test_onscreen_advisory_stripped(self):
        text = (
            "Some text.\n\n"
            "On-screen advisory (VO): This film draws on sources.\n\n"
            "More text."
        )
        result = format_elevenlabs(text)
        assert "On-screen advisory" not in result
        assert "More text." in result

    def test_disclaimer_stripped(self):
        text = "Good ending.\n\nThis documentary script is a historical synthesis based on cited sources."
        result = format_elevenlabs(text)
        assert "historical synthesis" not in result
        assert "Good ending." in result

    def test_cta_block_stripped(self):
        text = (
            "Strong ending.\n\n"
            "--- [CTA] ---\n\n"
            "Next we follow a briefcase. Stay with us."
        )
        result = format_elevenlabs(text)
        assert "CTA" not in result
        assert "Stay with us" not in result
        assert "Strong ending." in result

    def test_timestamps_stripped(self):
        text = "T-48:00 (June 4, 1944, 22:00) — London. A wall clock ticked."
        result = format_elevenlabs(text)
        assert "T-48:00" not in result
        assert "wall clock ticked" in result

    def test_timestamp_variants_stripped(self):
        text = "T-00:00 to T-? — The window opened."
        result = format_elevenlabs(text)
        assert "T-00:00" not in result
        assert "T-?" not in result

    def test_according_to_wikipedia_stripped(self):
        text = "According to Wikipedia, Harris was an MI5 officer."
        result = format_elevenlabs(text)
        assert "According to Wikipedia" not in result
        assert "Harris" in result

    def test_according_to_wikipedia_biography_stripped(self):
        text = "According to Wikipedia's Juan Pujol García biography, Pujol built a network."
        result = format_elevenlabs(text)
        assert "According to Wikipedia" not in result
        assert "Pujol built a network" in result

    def test_according_to_wikipedia_entry_stripped(self):
        text = "According to Wikipedia's Juan Pujol García entry, he served as a double agent."
        result = format_elevenlabs(text)
        assert "According to Wikipedia" not in result
        assert "he served as a double agent" in result

    def test_wikipedia_says_stripped(self):
        text = "Wikipedia says that the operation lasted 40 minutes."
        result = format_elevenlabs(text)
        assert "Wikipedia" not in result
        assert "the operation lasted 40 minutes" in result

    def test_wikipedia_states_stripped(self):
        text = "Wikipedia states the team returned to Afghanistan."
        result = format_elevenlabs(text)
        assert "Wikipedia" not in result
        assert "the team returned to Afghanistan" in result


# ─── Hedge Deduplication ─────────────────────────────────────


class TestHedgeDeduplication:
    """Verify that excessive hedge phrases are stripped."""

    def test_first_two_hedges_kept(self):
        text = (
            "Evidence suggests Potiorek imposed emergency measures. "
            "Records show the parliament was dissolved."
        )
        result = _deduplicate_hedges(text)
        assert "Evidence suggests" in result
        assert "Records show" in result

    def test_third_hedge_stripped(self):
        text = (
            "Evidence suggests Potiorek imposed emergency measures. "
            "Records show the parliament was dissolved. "
            "The evidence suggests the driver was not informed."
        )
        result = _deduplicate_hedges(text)
        # First two kept
        assert "Evidence suggests" in result
        assert "Records show" in result
        # Third stripped — but the factual content remains (capitalised)
        assert "driver was not informed" in result
        # Count total hedge occurrences — should be at most 2
        import re
        count = len(re.findall(
            r"(?:evidence suggests|records show|records indicate|evidence points? to)",
            result,
            re.IGNORECASE,
        ))
        assert count <= 2

    def test_many_hedges_reduced(self):
        sentences = [
            "Evidence suggests Potiorek acted.",
            "The evidence suggests the plan failed.",
            "Records show the route changed.",
            "The evidence points to a conspiracy.",
            "Records indicate six attackers.",
        ]
        text = " ".join(sentences)
        result = _deduplicate_hedges(text)
        import re
        count = len(re.findall(
            r"(?:evidence suggests|records show|records indicate|evidence points? to)",
            result,
            re.IGNORECASE,
        ))
        assert count <= 2
        # All factual content preserved (may be capitalised after hedge removal)
        assert "Potiorek acted" in result
        assert "plan failed" in result
        assert "route changed" in result
        assert "conspiracy" in result
        assert "attackers" in result

    def test_no_hedges_unchanged(self):
        text = "Potiorek imposed emergency measures in 1913."
        result = _deduplicate_hedges(text)
        assert result == text


# ─── TTS Normalisation ──────────────────────────────────────


class TestNormalisation:
    """Text should be cleaned for TTS engine consumption."""

    def test_mi5_expanded(self):
        result = _normalise_for_tts("MI5 recruited him.")
        assert "M.I. Five" in result

    def test_mi6_expanded(self):
        result = _normalise_for_tts("MI6 sent a cable.")
        assert "M.I. Six" in result

    def test_smart_quotes_converted(self):
        result = _normalise_for_tts("\u201cHello,\u201d she said.")
        assert '"Hello,"' in result

    def test_bold_markdown_stripped(self):
        result = _normalise_for_tts("The **real** story.")
        assert "**" not in result
        assert "real" in result

    def test_pas_de_calais_phonetic(self):
        result = _normalise_for_tts("forces near Pas-de-Calais.")
        assert "Pah-de-Callay" in result


# ─── Emphasis ────────────────────────────────────────────────


class TestEmphasis:
    """Key payoff words should be capitalised for vocal stress."""

    def test_never_again(self):
        result = _apply_emphasis("He would never again ask.")
        assert "NEVER again" in result

    def test_good_of_humanity(self):
        result = _apply_emphasis("for the good of humanity.")
        assert "GOOD of humanity" in result

    def test_risk_everything(self):
        result = _apply_emphasis("He would risk everything.")
        assert "risk EVERYTHING" in result

    def test_network_held(self):
        result = _apply_emphasis("The network held.")
        assert "network HELD" in result

    def test_twenty_seven(self):
        result = _apply_emphasis("Twenty-seven agents stood ready.")
        assert "TWENTY-SEVEN" in result


# ─── Pacing ──────────────────────────────────────────────────


class TestPacing:
    """Breaks and pauses should be inserted for natural delivery."""

    def test_paragraph_break_inserts_pause(self):
        text = "First paragraph.\n\nSecond paragraph."
        result = _apply_pacing(text)
        assert '<break time="1.5s" />' in result

    def test_em_dash_becomes_ellipsis(self):
        text = "Harris's cigarette—Players Navy Cut—left a blister."
        result = _apply_pacing(text)
        assert "—" not in result
        assert "…" in result

    def test_staccato_by_pattern(self):
        text = "You count it by absences. By units. By orders."
        result = _apply_pacing(text)
        assert '<break time="0.3s" />' in result

    def test_close_enough_staccato(self):
        text = "Close enough that Harris cut adverbs. Close enough that GARBO crossed out a name."
        result = _apply_pacing(text)
        assert '<break time="0.4s" />' in result


# ─── Dialogue Treatment ─────────────────────────────────────


class TestDialogue:
    """Quoted speech should get a micro-pause before it."""

    def test_pause_before_quote(self):
        text = 'he said. "Windows are tight."'
        result = _treat_dialogue(text)
        assert '<break time="0.3s" />' in result


# ─── Sentence Classification ────────────────────────────────


class TestClassification:
    """Sentences should be classified into the correct emotional mode."""

    def test_question_classified_curious(self):
        tag = _classify_sentence("What, exactly, did he say?")
        assert tag == "[curious]"

    def test_tension_classified(self):
        tag = _classify_sentence("If he warned too soon, the armada would fail.")
        assert tag == "[tense]"

    def test_solemn_classified(self):
        tag = _classify_sentence("What endures here is a plain truth.")
        assert tag == "[solemn]"

    def test_resolve_classified(self):
        tag = _classify_sentence("He decided two things that night.")
        assert tag == "[resolute]"

    def test_climax_classified(self):
        tag = _classify_sentence("Dawn broke over Normandy.")
        assert tag == "[intense]"

    def test_neutral_returns_none(self):
        tag = _classify_sentence("The table had a folded signal pad.")
        assert tag is None


# ─── First Sentence Extraction ───────────────────────────────


class TestFirstSentence:
    """The first sentence should be correctly isolated."""

    def test_simple_extraction(self):
        s = _extract_first_sentence("First sentence. Second sentence.")
        assert s == "First sentence."

    def test_question_extraction(self):
        s = _extract_first_sentence("What happened? Nobody knew.")
        assert s == "What happened?"


# ─── Full Pipeline Integration ───────────────────────────────


class TestFullPipeline:
    """End-to-end tests on realistic script fragments."""

    SAMPLE_SCRIPT = (
        "# Test Title\n\n"
        "--- [Opening (0–20s)] ---\n\n"
        "T-20:00 (June 6, 02:00). London. Juan Pujol Garcia cupped one ear. "
        'He would risk everything on one perfectly wrong message. '
        "What, exactly, did he say?\n\n"
        "Re-hook: The door closes.\n\n"
        "--- [Act 1: Setup + first complication] ---\n\n"
        'Harris said. "Sound Madrid-born." '
        "The MI5 handler leaned in.\n\n"
        "He decided two things that night. He would never again ask for permission.\n\n"
        "--- [The Gut Punch] ---\n\n"
        "Picture a duty officer's finger hovering.\n\n"
        "--- [Closing Loop Callback] ---\n\n"
        "The network held. What endures here is a plain truth.\n\n"
        "--- [CTA] ---\n\n"
        "Next we follow a briefcase. Stay with us.\n\n"
        "This documentary script is a historical synthesis based on cited sources."
    )

    def test_no_structural_markers(self):
        result = format_elevenlabs(self.SAMPLE_SCRIPT)
        assert "---" not in result
        assert "Re-hook" not in result
        assert "CTA" not in result
        assert "Opening" not in result.split("\n")[0] if result else True

    def test_no_timestamps(self):
        result = format_elevenlabs(self.SAMPLE_SCRIPT)
        assert "T-20:00" not in result

    def test_no_disclaimer(self):
        result = format_elevenlabs(self.SAMPLE_SCRIPT)
        assert "historical synthesis" not in result

    def test_mi5_expanded(self):
        result = format_elevenlabs(self.SAMPLE_SCRIPT)
        assert "M.I. Five" in result

    def test_emphasis_applied(self):
        result = format_elevenlabs(self.SAMPLE_SCRIPT)
        assert "risk EVERYTHING" in result
        assert "NEVER again" in result

    def test_has_audio_tags(self):
        result = format_elevenlabs(self.SAMPLE_SCRIPT)
        # Should have at least one audio tag
        assert re.search(r"\[(?:curious|tense|solemn|resolute|intense|intrigued)\]", result)

    def test_has_break_tags(self):
        result = format_elevenlabs(self.SAMPLE_SCRIPT)
        assert "<break time=" in result

    def test_no_cta_content(self):
        result = format_elevenlabs(self.SAMPLE_SCRIPT)
        assert "Stay with us" not in result
        assert "briefcase" not in result

    def test_output_is_clean_text(self):
        result = format_elevenlabs(self.SAMPLE_SCRIPT)
        # No markdown artefacts
        assert "# " not in result
        assert "**" not in result

    def test_dialogue_gets_pause(self):
        result = format_elevenlabs(self.SAMPLE_SCRIPT)
        # The quote after "Harris said." should have a break
        assert '<break time="0.3s" />' in result
