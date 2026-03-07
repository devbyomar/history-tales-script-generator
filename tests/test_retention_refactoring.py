"""Unit tests for YouTube retention refactoring changes.

Tests cover:
 - Anti-poetic pattern validator
 - Sentence length validator
 - Fact repetition validator
 - Exposition density validator
 - Timeline structure validator
 - New state fields (ScriptSection, QCReport, AgentState)

Run with:  pytest tests/test_retention_refactoring.py -v
"""

from __future__ import annotations

import pytest

from history_tales_agent.validators import (
    ValidationIssue,
    validate_anti_poetic_patterns,
    validate_sentence_length,
    validate_fact_repetition,
    validate_exposition_density,
    validate_timeline_structure,
)
from history_tales_agent.state import (
    AgentState,
    QCReport,
    ScriptSection,
)


# ──────────────────────────────────────────────────────────────────────────
# Anti-poetic pattern validator
# ──────────────────────────────────────────────────────────────────────────


class TestAntiPoeticPatterns:
    """Tests for validate_anti_poetic_patterns()."""

    def test_clean_text_no_issues(self):
        script = (
            "He lied. Three people died because of it. "
            "The fighting lasted eleven days. Nobody spoke. The order stood."
        )
        issues = validate_anti_poetic_patterns(script)
        assert len(issues) == 0

    def test_noun_of_abstract(self):
        script = "The architecture of betrayal was clear to everyone."
        issues = validate_anti_poetic_patterns(script)
        codes = [i.code for i in issues]
        assert "ANTIPOETIC_NOUN_OF_ABSTRACT" in codes

    def test_noun_of_abstract_variants(self):
        script = (
            "The geometry of deception fooled them all. "
            "The machinery of control ground them down."
        )
        issues = validate_anti_poetic_patterns(script)
        noun_issues = [i for i in issues if i.code == "ANTIPOETIC_NOUN_OF_ABSTRACT"]
        assert len(noun_issues) >= 2

    def test_not_x_was_y_pivot(self):
        script = "This was not a war — it was a reckoning that changed everything."
        issues = validate_anti_poetic_patterns(script)
        codes = [i.code for i in issues]
        assert "ANTIPOETIC_NOT_X_WAS_Y" in codes

    def test_noun_as_verb(self):
        script = "History telescoped into a single afternoon of violence."
        issues = validate_anti_poetic_patterns(script)
        codes = [i.code for i in issues]
        assert "ANTIPOETIC_NOUN_AS_VERB" in codes

    def test_decorative_personification(self):
        script = "Silence carried more weight than any order ever could."
        issues = validate_anti_poetic_patterns(script)
        codes = [i.code for i in issues]
        assert "ANTIPOETIC_PERSONIFICATION" in codes

    def test_personification_variants(self):
        script = (
            "Fear gripped the entire city. "
            "Death waited outside the door. "
            "Time crept forward slowly."
        )
        issues = validate_anti_poetic_patterns(script)
        pers_issues = [i for i in issues if i.code == "ANTIPOETIC_PERSONIFICATION"]
        assert len(pers_issues) >= 2

    def test_poetic_thesis_closing(self):
        script = (
            "And in the silence that followed, the world learned that courage "
            "is not the absence of fear but the decision to act despite it."
        )
        issues = validate_anti_poetic_patterns(script)
        codes = [i.code for i in issues]
        assert "ANTIPOETIC_POETIC_CLOSING" in codes

    def test_poetic_closing_perhaps(self):
        script = "Perhaps the lesson is that no one is truly safe."
        issues = validate_anti_poetic_patterns(script)
        codes = [i.code for i in issues]
        assert "ANTIPOETIC_POETIC_CLOSING" in codes

    def test_poetic_closing_history_would_remember(self):
        script = "History would remember this as the turning point."
        issues = validate_anti_poetic_patterns(script)
        codes = [i.code for i in issues]
        assert "ANTIPOETIC_POETIC_CLOSING" in codes

    def test_clause_chain_sentence(self):
        script = (
            "Across the frozen steppe, through columns of smoke, past the "
            "wreckage of a dozen villages, beyond the river crossing, the "
            "convoy pressed forward into the unknown darkness ahead."
        )
        issues = validate_anti_poetic_patterns(script)
        codes = [i.code for i in issues]
        assert "ANTIPOETIC_CLAUSE_CHAIN" in codes

    def test_summary_issue_present(self):
        script = "The architecture of betrayal was complete."
        issues = validate_anti_poetic_patterns(script)
        summary = [i for i in issues if i.code == "ANTIPOETIC_SUMMARY"]
        assert len(summary) == 1
        assert "violation" in summary[0].message.lower()

    def test_no_summary_when_clean(self):
        script = "He signed the paper. The war was over."
        issues = validate_anti_poetic_patterns(script)
        summary = [i for i in issues if i.code == "ANTIPOETIC_SUMMARY"]
        assert len(summary) == 0

    def test_max_flagged_per_pattern(self):
        # Generate many violations of the same pattern
        script = " ".join(
            f"The architecture of betrayal number {i}." for i in range(20)
        )
        issues = validate_anti_poetic_patterns(script, max_flagged_per_pattern=3)
        noun_issues = [i for i in issues if i.code == "ANTIPOETIC_NOUN_OF_ABSTRACT"]
        assert len(noun_issues) <= 3

    def test_multiple_patterns_in_one_script(self):
        script = (
            "The geometry of deception was obvious. "
            "It was not a war — it was a reckoning. "
            "Silence carried more weight than any order. "
            "History would remember this day forever."
        )
        issues = validate_anti_poetic_patterns(script)
        codes = {i.code for i in issues}
        # Should catch at least 3 different pattern types + summary
        assert "ANTIPOETIC_SUMMARY" in codes
        assert len(codes) >= 3


# ──────────────────────────────────────────────────────────────────────────
# Sentence length validator
# ──────────────────────────────────────────────────────────────────────────


class TestSentenceLength:
    """Tests for validate_sentence_length()."""

    def test_short_sentences_no_issues(self):
        script = "He ran. The door was locked. She waited outside."
        issues = validate_sentence_length(script)
        assert len(issues) == 0

    def test_flags_long_sentence(self):
        long = " ".join(["word"] * 30)
        script = f"Short sentence here. {long} and more words to finish this very long thought indeed."
        issues = validate_sentence_length(script, hard_ceiling=25)
        over_limit = [i for i in issues if i.code == "SENTENCE_OVER_LIMIT"]
        assert len(over_limit) >= 1

    def test_average_too_high(self):
        # All sentences ~22 words → average above 20
        sent = " ".join(["word"] * 22) + "."
        script = " ".join([sent] * 10)
        issues = validate_sentence_length(script, hard_ceiling=50, avg_ceiling=20)
        avg_issues = [i for i in issues if i.code == "SENTENCE_AVG_HIGH"]
        assert len(avg_issues) == 1

    def test_max_flagged_respected(self):
        long = " ".join(["word"] * 30) + "."
        script = " ".join([long] * 20)
        issues = validate_sentence_length(script, hard_ceiling=25, max_flagged=3)
        over_limit = [i for i in issues if i.code == "SENTENCE_OVER_LIMIT"]
        assert len(over_limit) <= 3


# ──────────────────────────────────────────────────────────────────────────
# Fact repetition validator
# ──────────────────────────────────────────────────────────────────────────


class TestFactRepetition:
    """Tests for validate_fact_repetition()."""

    def test_no_repetition(self):
        script = "Each sentence is unique. Nothing repeats here."
        issues = validate_fact_repetition(script)
        assert len(issues) == 0

    def test_flags_repeated_phrase(self):
        script = (
            "seventeen escape attempts were recorded that year. "
            "Later that month seventeen escape attempts were recorded again. "
            "In total seventeen escape attempts were recorded across the camp."
        )
        issues = validate_fact_repetition(script)
        rep_issues = [i for i in issues if i.code == "FACT_REPETITION"]
        assert len(rep_issues) >= 1

    def test_short_text_no_crash(self):
        script = "Short."
        issues = validate_fact_repetition(script)
        assert issues == []


# ──────────────────────────────────────────────────────────────────────────
# Exposition density validator
# ──────────────────────────────────────────────────────────────────────────


class TestExpositionDensity:
    """Tests for validate_exposition_density()."""

    def test_action_paragraphs_no_issues(self):
        script = (
            "General Eisenhower stood in the rain and decided to proceed. "
            "He signed the order without hesitation.\n\n"
            "Field Marshal Montgomery watched from across the room. "
            "The tension was visible on every face present."
        )
        issues = validate_exposition_density(script)
        assert len(issues) == 0

    def test_flags_consecutive_exposition(self):
        # 5 paragraphs of pure abstract text with no names, sensory, or action
        abstract = " ".join(["word"] * 50) + "."
        script = "\n\n".join([abstract] * 5)
        issues = validate_exposition_density(script, max_consecutive_exposition=3)
        drift_issues = [i for i in issues if i.code == "EXPOSITION_DRIFT"]
        assert len(drift_issues) >= 1


# ──────────────────────────────────────────────────────────────────────────
# Timeline structure validator
# ──────────────────────────────────────────────────────────────────────────


class TestTimelineStructure:
    """Tests for validate_timeline_structure()."""

    def test_good_timeline(self):
        beats = [
            {"tension_level": 3, "is_twist": False},
            {"tension_level": 5, "is_twist": False},
            {"tension_level": 7, "is_twist": True},
            {"tension_level": 8, "is_twist": False},
            {"tension_level": 9, "is_twist": True},
        ]
        issues = validate_timeline_structure(beats)
        assert len(issues) == 0

    def test_empty_timeline(self):
        issues = validate_timeline_structure([])
        codes = [i.code for i in issues]
        assert "TIMELINE_EMPTY" in codes
        # Should be hard severity
        assert any(i.severity == "hard" for i in issues if i.code == "TIMELINE_EMPTY")

    def test_too_few_beats(self):
        beats = [{"tension_level": 5, "is_twist": True}]
        issues = validate_timeline_structure(beats, min_beats=4)
        codes = [i.code for i in issues]
        assert "TIMELINE_TOO_SHORT" in codes

    def test_no_twists(self):
        beats = [
            {"tension_level": 3, "is_twist": False},
            {"tension_level": 5, "is_twist": False},
            {"tension_level": 7, "is_twist": False},
            {"tension_level": 8, "is_twist": False},
        ]
        issues = validate_timeline_structure(beats, min_twists=1)
        codes = [i.code for i in issues]
        assert "TIMELINE_NO_TWISTS" in codes


# ──────────────────────────────────────────────────────────────────────────
# State schema tests for new fields
# ──────────────────────────────────────────────────────────────────────────


class TestNewStateFields:
    """Tests for new fields added to state models."""

    def test_script_section_midpoint_shift(self):
        s = ScriptSection(section_name="The Midpoint Shift")
        assert s.midpoint_shift == ""
        s2 = ScriptSection(
            section_name="The Midpoint Shift",
            midpoint_shift="New evidence recontextualises everything",
        )
        assert s2.midpoint_shift == "New evidence recontextualises everything"

    def test_script_section_late_pressure(self):
        s = ScriptSection(
            section_name="The Close",
            late_pressure="48-hour deadline before execution",
        )
        assert s.late_pressure == "48-hour deadline before execution"

    def test_script_section_final_thesis(self):
        s = ScriptSection(
            section_name="Final Line",
            final_thesis="He survived. The bridge held. 4000 crossed.",
        )
        assert s.final_thesis == "He survived. The bridge held. 4000 crossed."

    def test_qc_report_narratability_score(self):
        r = QCReport()
        assert r.narratability_score == 0.0
        r2 = QCReport(narratability_score=85.5)
        assert r2.narratability_score == 85.5

    def test_agent_state_words_per_minute(self):
        s = AgentState(video_length_minutes=12)
        assert s.words_per_minute == 155

    def test_agent_state_words_per_minute_custom(self):
        s = AgentState(video_length_minutes=12, words_per_minute=115)
        assert s.words_per_minute == 115

    def test_agent_state_narratability_score(self):
        s = AgentState(video_length_minutes=12)
        assert s.narratability_score == 0.0
        s2 = AgentState(video_length_minutes=12, narratability_score=78.0)
        assert s2.narratability_score == 78.0

    def test_agent_state_output_mode(self):
        s = AgentState(video_length_minutes=12, output_mode="speechify_export")
        assert s.output_mode == "speechify_export"


# ──────────────────────────────────────────────────────────────────────────
# Integration: anti-poetic validator wired into post-script validation
# ──────────────────────────────────────────────────────────────────────────


class TestPostScriptAntiPoeticIntegration:
    """Verify anti-poetic patterns are caught in run_post_script_validation."""

    def test_anti_poetic_in_post_validation(self):
        from history_tales_agent.validators import run_post_script_validation

        # Script with an anti-poetic violation
        script = (
            "General Dwight Eisenhower faced the architecture of betrayal. "
            "He signed the order. The wind howled? " * 50
        )
        claims = [
            {"claim_id": "C001", "claim_text": "Eisenhower ordered", "named_entities": ["Dwight Eisenhower"]},
        ]
        beats = [{"event": "Eisenhower orders", "pov": "Dwight Eisenhower"}]
        word_count = len(script.split())

        report = run_post_script_validation(
            script=script,
            verified_claims=claims,
            timeline_beats=beats,
            min_words=100,
            max_words=word_count + 100,
            rehook_words=200,
        )
        codes = [i.code for i in report.issues]
        assert "ANTIPOETIC_NOUN_OF_ABSTRACT" in codes or "ANTIPOETIC_SUMMARY" in codes
