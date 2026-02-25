"""Unit tests for history_tales_agent.validators.

Tests cover every validator function and schema defined in validators.py.
Run with:  pytest tests/test_validators.py -v
"""

from __future__ import annotations

import pytest

from history_tales_agent.validators import (
    ClaimArtifact,
    CrossCheckedClaim,
    OutlineSectionArtifact,
    RehookPlanItem,
    TimelineBeatArtifact,
    ValidationIssue,
    ValidationReport,
    build_entity_allowlist,
    extract_named_humans,
    extract_trace_tags,
    run_post_script_validation,
    run_pre_script_validation,
    strip_trace_tags,
    validate_entity_provenance,
    validate_essay_blocks,
    validate_open_loops,
    validate_outline_word_sum,
    validate_rehook_cadence,
    validate_retention_no_new_entities,
    validate_tension_escalation,
    validate_twist_distribution,
    validate_word_count,
)


# ──────────────────────────────────────────────────────────────────────────
# Schema instantiation tests
# ──────────────────────────────────────────────────────────────────────────


class TestSchemas:
    def test_claim_artifact_defaults(self):
        c = ClaimArtifact(claim_text="Test claim")
        assert c.claim_id == ""
        assert c.source_type == "Secondary"
        assert c.confidence == "Moderate"
        assert c.named_entities == []
        assert c.quote_candidate is False
        assert c.date_anchor == ""

    def test_claim_artifact_full(self):
        c = ClaimArtifact(
            claim_id="C001",
            claim_text="Eisenhower ordered the invasion",
            source_type="Primary",
            confidence="High",
            date_anchor="1944-06-06",
            named_entities=["Dwight Eisenhower"],
            quote_candidate=True,
        )
        assert c.claim_id == "C001"
        assert c.named_entities == ["Dwight Eisenhower"]
        assert c.quote_candidate is True

    def test_cross_checked_claim(self):
        c = CrossCheckedClaim(
            claim_id="C001",
            claim_text="Test",
            script_language="According to military records, the order was issued at dawn.",
        )
        assert c.script_language.startswith("According")
        assert c.claim_id == "C001"

    def test_timeline_beat_artifact(self):
        b = TimelineBeatArtifact(event="Attack begins", tension_level=7, is_twist=True)
        assert b.tension_level == 7
        assert b.is_twist is True

    def test_outline_section_artifact(self):
        s = OutlineSectionArtifact(
            section_name="Opening",
            target_word_count=120,
            minute_range="0:00–0:20",
            rehook_plan=[RehookPlanItem(approx_word_index=50, purpose="open loop")],
        )
        assert s.minute_range == "0:00–0:20"
        assert len(s.rehook_plan) == 1

    def test_validation_report_add(self):
        r = ValidationReport()
        assert r.passed is True
        r.add("TEST_SOFT", "A soft issue", severity="soft")
        assert r.passed is True
        r.add("TEST_HARD", "A hard issue", severity="hard")
        assert r.passed is False
        assert len(r.hard_issues) == 1
        assert len(r.soft_issues) == 1


# ──────────────────────────────────────────────────────────────────────────
# Named-entity extraction
# ──────────────────────────────────────────────────────────────────────────


class TestExtractNamedHumans:
    def test_simple_names(self):
        text = "General Dwight Eisenhower gave the order. Winston Churchill agreed."
        names = extract_named_humans(text)
        # Regex is recall-biased: may capture "General Dwight Eisenhower" as a full match
        assert any("Eisenhower" in n for n in names)
        assert "Winston Churchill" in names

    def test_ignores_single_word(self):
        text = "The general was named Eisenhower."
        names = extract_named_humans(text)
        # Single capitalised word should not be extracted
        assert len(names) == 0

    def test_section_markers_stripped(self):
        text = "--- [OPENING] --- John Smith walked in."
        names = extract_named_humans(text)
        assert "John Smith" in names

    def test_no_false_positives_from_title_words(self):
        text = "The Act Of Parliament was debated."
        names = extract_named_humans(text)
        # "Act Of" should not be extracted as a name
        assert len(names) == 0

    def test_names_with_particles(self):
        text = "Ludwig van Beethoven composed the piece."
        names = extract_named_humans(text)
        assert any("Beethoven" in n for n in names)


class TestBuildEntityAllowlist:
    def test_from_claims_and_beats(self):
        claims = [
            {"claim_text": "Erwin Rommel commanded the defense", "named_entities": ["Erwin Rommel"]},
            {"claim_text": "Omar Bradley led the assault", "named_entities": []},
        ]
        beats = [
            {"event": "Eisenhower makes the call", "pov": "Dwight Eisenhower"},
        ]
        allowed = build_entity_allowlist(claims, beats)
        assert "Erwin Rommel" in allowed
        assert "Dwight Eisenhower" in allowed
        assert "Omar Bradley" in allowed


# ──────────────────────────────────────────────────────────────────────────
# Entity provenance validator
# ──────────────────────────────────────────────────────────────────────────


class TestEntityProvenance:
    def test_no_issues_when_all_in_claims(self):
        claims = [{"claim_text": "John Smith acted", "named_entities": ["John Smith"]}]
        beats = [{"event": "something", "pov": "John Smith"}]
        script = "John Smith opened the door."
        issues = validate_entity_provenance(script, claims, beats)
        assert len(issues) == 0

    def test_flags_unknown_entity(self):
        claims = [{"claim_text": "John Smith acted", "named_entities": ["John Smith"]}]
        beats = []
        script = "John Smith and Robert Jones opened the door."
        issues = validate_entity_provenance(script, claims, beats)
        flagged_names = [i.message for i in issues]
        assert any("Robert Jones" in m for m in flagged_names)


# ──────────────────────────────────────────────────────────────────────────
# Word count validator
# ──────────────────────────────────────────────────────────────────────────


class TestWordCount:
    def test_within_range(self):
        script = " ".join(["word"] * 1860)
        issues = validate_word_count(script, 1674, 2046)
        assert len(issues) == 0

    def test_under_range(self):
        script = " ".join(["word"] * 100)
        issues = validate_word_count(script, 1674, 2046)
        assert len(issues) == 1
        assert issues[0].code == "WORD_COUNT_UNDER"

    def test_over_range(self):
        script = " ".join(["word"] * 3000)
        issues = validate_word_count(script, 1674, 2046)
        assert len(issues) == 1
        assert issues[0].code == "WORD_COUNT_OVER"


# ──────────────────────────────────────────────────────────────────────────
# Rehook cadence validator
# ──────────────────────────────────────────────────────────────────────────


class TestRehookCadence:
    def test_no_issues_with_frequent_questions(self):
        words = ["word"] * 50 + ["question?"] + ["word"] * 50
        script = " ".join(words)
        issues = validate_rehook_cadence(script, rehook_words=200)
        assert len(issues) == 0

    def test_flags_long_gap(self):
        # 300 words with no rehook signal
        script = " ".join(["word"] * 300)
        issues = validate_rehook_cadence(script, rehook_words=100)
        assert any(i.code == "REHOOK_GAP" for i in issues)


# ──────────────────────────────────────────────────────────────────────────
# Open-loop validator
# ──────────────────────────────────────────────────────────────────────────


class TestOpenLoops:
    def test_resolved_loops_no_issues(self):
        sections = [
            {"open_loops": ["who was the spy?"], "key_beats": [], "re_hooks": []},
            {"open_loops": [], "key_beats": ["who was the spy?"], "re_hooks": []},
        ]
        issues = validate_open_loops(sections)
        assert len(issues) == 0

    def test_unresolved_loop_flagged(self):
        sections = [
            {"open_loops": ["who was the spy?"], "key_beats": [], "re_hooks": []},
            {"open_loops": [], "key_beats": [], "re_hooks": []},
            {"open_loops": [], "key_beats": [], "re_hooks": []},
            {"open_loops": [], "key_beats": [], "re_hooks": []},
        ]
        issues = validate_open_loops(sections)
        assert any(i.code == "OPEN_LOOP_UNRESOLVED" for i in issues)


# ──────────────────────────────────────────────────────────────────────────
# Essay-block validator
# ──────────────────────────────────────────────────────────────────────────


class TestEssayBlocks:
    def test_no_issue_with_names_and_sensory(self):
        text = (
            "General Dwight Eisenhower looked out the rain-soaked window and decided "
            "to launch the attack. The cold wind howled outside as he signed the papers. "
        ) * 3  # well over 60 words
        issues = validate_essay_blocks(text)
        assert len(issues) == 0

    def test_flags_abstract_block(self):
        # 80+ words of pure abstraction
        text = " ".join(
            ["the", "importance", "of", "understanding", "geopolitical", "dynamics",
             "cannot", "be", "overstated", "because"] * 8
        )
        issues = validate_essay_blocks(text)
        assert any(i.code == "ESSAY_BLOCK" for i in issues)


# ──────────────────────────────────────────────────────────────────────────
# Tension escalation validator
# ──────────────────────────────────────────────────────────────────────────


class TestTensionEscalation:
    def test_perfectly_escalating(self):
        beats = [{"tension_level": i} for i in range(1, 11)]
        issues = validate_tension_escalation(beats)
        assert len(issues) == 0

    def test_allows_two_dips(self):
        beats = [
            {"tension_level": 3},
            {"tension_level": 2},  # dip 1
            {"tension_level": 5},  # +3 spike — ok
            {"tension_level": 6},
            {"tension_level": 5},  # dip 2
            {"tension_level": 8},  # +3 spike — ok
            {"tension_level": 9},
        ]
        # Expect no TENSION_TOO_MANY_DIPS (only 2 non-increasing)
        hard_issues = [i for i in validate_tension_escalation(beats) if i.code == "TENSION_TOO_MANY_DIPS"]
        assert len(hard_issues) == 0

    def test_flags_third_dip(self):
        beats = [
            {"tension_level": 3},
            {"tension_level": 2},  # dip 1
            {"tension_level": 5},
            {"tension_level": 4},  # dip 2
            {"tension_level": 7},
            {"tension_level": 6},  # dip 3 — should flag
            {"tension_level": 9},
        ]
        hard_issues = [i for i in validate_tension_escalation(beats) if i.code == "TENSION_TOO_MANY_DIPS"]
        assert len(hard_issues) >= 1

    def test_flags_dip_without_spike(self):
        beats = [
            {"tension_level": 5},
            {"tension_level": 3},  # dip
            {"tension_level": 4},  # only +1, need +2
            {"tension_level": 6},
        ]
        spike_issues = [i for i in validate_tension_escalation(beats) if i.code == "TENSION_NO_SPIKE_AFTER_DIP"]
        assert len(spike_issues) >= 1


# ──────────────────────────────────────────────────────────────────────────
# Twist distribution validator
# ──────────────────────────────────────────────────────────────────────────


class TestTwistDistribution:
    def test_good_distribution(self):
        # 10 beats, twists at indices 3,4,5 (Act 2 = 30-70% = indices 3-7)
        beats = [{"is_twist": (i in {3, 4, 5})} for i in range(10)]
        issues = validate_twist_distribution(beats)
        assert len(issues) == 0

    def test_skewed_distribution(self):
        # All twists at start
        beats = [{"is_twist": (i < 2)} for i in range(10)]
        issues = validate_twist_distribution(beats)
        assert any(i.code == "TWIST_DISTRIBUTION_SKEWED" for i in issues)

    def test_no_twists(self):
        beats = [{"is_twist": False} for _ in range(10)]
        issues = validate_twist_distribution(beats)
        assert any(i.code == "NO_TWISTS" for i in issues)


# ──────────────────────────────────────────────────────────────────────────
# Outline word-sum validator
# ──────────────────────────────────────────────────────────────────────────


class TestOutlineWordSum:
    def test_exact_match(self):
        sections = [
            {"target_word_count": 600},
            {"target_word_count": 600},
            {"target_word_count": 660},
        ]
        issues = validate_outline_word_sum(sections, target_words=1860)
        assert len(issues) == 0

    def test_within_tolerance(self):
        sections = [
            {"target_word_count": 600},
            {"target_word_count": 600},
            {"target_word_count": 500},
        ]
        # 1700 vs 1860 target — 1700/1860 = 91.4% — within ±10% (1674-2046)
        issues = validate_outline_word_sum(sections, target_words=1860)
        assert len(issues) == 0

    def test_way_off(self):
        sections = [{"target_word_count": 100}]
        issues = validate_outline_word_sum(sections, target_words=1860)
        assert any(i.code == "OUTLINE_WORD_SUM_MISMATCH" for i in issues)


# ──────────────────────────────────────────────────────────────────────────
# Trace-tag utilities
# ──────────────────────────────────────────────────────────────────────────


class TestTraceTags:
    def test_strip_trace_tags(self):
        text = "The battle raged on. [Beat B03 | Claims C001,C002] The general ordered retreat."
        stripped = strip_trace_tags(text)
        assert "[Beat" not in stripped
        assert "The battle raged on." in stripped
        assert "The general ordered retreat." in stripped

    def test_extract_trace_tags(self):
        text = "Para one. [Beat B01 | Claims C001,C003]\n\nPara two. [Beat B02 | Claims C002]"
        tags = extract_trace_tags(text)
        assert len(tags) == 2
        assert tags[0]["beat"] == "B01"
        assert "C001" in tags[0]["claims"]
        assert "C003" in tags[0]["claims"]

    def test_strip_preserves_clean_text(self):
        text = "No tags here. Just normal text."
        assert strip_trace_tags(text) == text


# ──────────────────────────────────────────────────────────────────────────
# Retention entity guard
# ──────────────────────────────────────────────────────────────────────────


class TestRetentionNoNewEntities:
    def test_no_issues_same_entities(self):
        original = "John Smith walked through the door."
        revised = "John Smith opened the heavy door."
        issues = validate_retention_no_new_entities(original, revised)
        assert len(issues) == 0

    def test_flags_new_entity(self):
        original = "John Smith walked through the door."
        revised = "John Smith and Robert Jones walked through the door."
        issues = validate_retention_no_new_entities(original, revised)
        assert any("Robert Jones" in i.message for i in issues)


# ──────────────────────────────────────────────────────────────────────────
# Integration: pre-script validation
# ──────────────────────────────────────────────────────────────────────────


class TestPreScriptValidation:
    def test_clean_pass(self):
        outline = [
            {
                "section_name": "Opening",
                "target_word_count": 900,
                "open_loops": ["who is the spy?"],
                "key_beats": [],
                "re_hooks": [],
            },
            {
                "section_name": "Act 1",
                "target_word_count": 960,
                "open_loops": [],
                "key_beats": ["who is the spy?"],
                "re_hooks": [],
            },
        ]
        beats = [
            {"tension_level": i + 1, "is_twist": (i == 3)}
            for i in range(6)
        ]
        claims = [{"claim_id": "C001", "claim_text": "test", "named_entities": []}]

        report = run_pre_script_validation(
            outline_sections=outline,
            timeline_beats=beats,
            verified_claims=claims,
            target_words=1860,
            rehook_words=200,
        )
        # Should pass (outline sums to 1860, loop resolved, tension escalates)
        assert report.passed is True

    def test_flags_word_sum_mismatch(self):
        outline = [{"section_name": "X", "target_word_count": 100, "open_loops": [], "key_beats": [], "re_hooks": []}]
        beats = [{"tension_level": i + 1, "is_twist": False} for i in range(5)]
        claims = []

        report = run_pre_script_validation(
            outline_sections=outline,
            timeline_beats=beats,
            verified_claims=claims,
            target_words=1860,
            rehook_words=200,
        )
        assert any(i.code == "OUTLINE_WORD_SUM_MISMATCH" for i in report.issues)


# ──────────────────────────────────────────────────────────────────────────
# Integration: post-script validation
# ──────────────────────────────────────────────────────────────────────────


class TestPostScriptValidation:
    def test_clean_pass(self):
        # Script with proper names, sensory detail, within word count
        lines = [
            "General Dwight Eisenhower stood in the cold rain and decided to proceed.",
            "The wind howled? He signed the order—",
        ]
        script = " ".join(lines * 50)  # repeat to get enough words

        claims = [
            {"claim_id": "C001", "claim_text": "Dwight Eisenhower ordered the invasion", "named_entities": ["Dwight Eisenhower"]},
        ]
        beats = [{"event": "Eisenhower orders invasion", "pov": "Dwight Eisenhower"}]

        word_count = len(script.split())
        report = run_post_script_validation(
            script=script,
            verified_claims=claims,
            timeline_beats=beats,
            min_words=100,
            max_words=word_count + 100,
            rehook_words=200,
        )
        # Should have no hard word-count issues
        wc_issues = [i for i in report.issues if i.code in ("WORD_COUNT_UNDER", "WORD_COUNT_OVER")]
        assert len(wc_issues) == 0
