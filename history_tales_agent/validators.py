"""Pydantic schemas for structured pipeline artifacts and deterministic validators.

Every JSON artifact returned by the LLM is parsed into one of these schemas.
Validator functions enforce hard constraints that the LLM cannot be trusted to
guarantee — word count, named-entity provenance, rehook cadence, open-loop
resolution, essay-block detection, tension escalation, and twist distribution.
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ────────────────────────────────────────────────────────────────────────────
# Artifact schemas (mirror what the LLM must return)
# ────────────────────────────────────────────────────────────────────────────


class ClaimArtifact(BaseModel):
    """Schema for a single claim returned by Claims Extraction."""

    claim_id: str = ""  # C001, C002, …
    claim_text: str
    source_type: str = "Secondary"
    confidence: str = "Moderate"
    needs_cross_check: bool = False
    date_anchor: str = ""  # e.g. "1944-06-06" or ""
    named_entities: list[str] = Field(default_factory=list)
    quote_candidate: bool = False


class CrossCheckedClaim(BaseModel):
    """Schema for a single claim after cross-checking."""

    claim_id: str = ""
    claim_text: str
    verified: bool = False
    confidence_after_check: str = "Moderate"
    supporting_sources: int = 0
    conflicting_info: str = ""
    recommended_treatment: str = ""
    script_language: str = ""  # safe narration sentence


class TimelineBeatArtifact(BaseModel):
    """Schema for a single timeline beat."""

    timestamp: str = ""
    event: str
    pov: str = ""
    tension_level: int = 0
    is_twist: bool = False
    open_loop: str = ""
    resolves_loop: str = ""


class RehookPlanItem(BaseModel):
    """A single planned re-hook inside a script outline section."""

    approx_word_index: int = 0
    purpose: str = ""
    line_stub: str = ""


class OutlineSectionArtifact(BaseModel):
    """Schema for a single outline section."""

    section_name: str
    description: str = ""
    target_word_count: int = 0
    minute_range: str = ""  # e.g. "0:00–0:20"
    re_hooks: list[str] = Field(default_factory=list)
    open_loops: list[str] = Field(default_factory=list)
    key_beats: list[str] = Field(default_factory=list)
    rehook_plan: list[RehookPlanItem] = Field(default_factory=list)


# ────────────────────────────────────────────────────────────────────────────
# Validation result
# ────────────────────────────────────────────────────────────────────────────


class ValidationIssue(BaseModel):
    """A single validation issue found by a guardrail."""

    code: str  # e.g. "ENTITY_NOT_IN_CLAIMS"
    severity: str = "hard"  # "hard" blocks pipeline, "soft" is advisory
    message: str = ""
    location: str = ""  # section or beat index


class ValidationReport(BaseModel):
    """Aggregated validation result returned by the Hard Guardrails node."""

    passed: bool = True
    issues: list[ValidationIssue] = Field(default_factory=list)

    def add(self, code: str, message: str, severity: str = "hard", location: str = "") -> None:
        self.issues.append(ValidationIssue(code=code, severity=severity, message=message, location=location))
        if severity == "hard":
            self.passed = False

    @property
    def hard_issues(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "hard"]

    @property
    def soft_issues(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "soft"]


# ────────────────────────────────────────────────────────────────────────────
# Utility: named-entity extraction (heuristic, no spaCy dependency)
# ────────────────────────────────────────────────────────────────────────────

# Common title words and generic terms that look like names but aren't
_TITLE_WORDS = {
    "the", "a", "an", "of", "and", "in", "at", "on", "to", "for", "by",
    "is", "was", "are", "were", "has", "had", "have", "will", "would",
    "but", "or", "not", "it", "he", "she", "they", "we", "his", "her",
    "its", "their", "our", "this", "that", "these", "those", "from",
    "with", "into", "what", "when", "where", "why", "how", "all",
    "act", "section", "opening", "closing", "cold", "open", "cta",
}

# Section markers used in scripts
_SECTION_MARKER_RE = re.compile(r"---\s*\[.*?\]\s*---")

# Capitalized multi-word sequence (heuristic for named humans)
_NAME_PATTERN = re.compile(
    r"\b([A-Z][a-z]+(?:\s+(?:de|von|van|al|el|ibn|bin|di|du|le|la|the|of))?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
)


def extract_named_humans(text: str) -> set[str]:
    """Extract likely human names from text using capitalisation heuristics.

    Returns a set of candidate full names (2+ capitalised words).  This is
    intentionally recall-biased — it may include place names; the caller
    cross-references against the allowlist to filter.
    """
    # Remove section markers
    cleaned = _SECTION_MARKER_RE.sub("", text)
    # Remove quoted strings (which may contain titles)
    cleaned = re.sub(r'"[^"]*"', "", cleaned)

    candidates: set[str] = set()
    for match in _NAME_PATTERN.finditer(cleaned):
        name = match.group(1).strip()
        tokens = name.split()
        # Filter: must have at least 2 real capitalised words (not just title-words)
        real = [t for t in tokens if t.lower() not in _TITLE_WORDS and len(t) > 1]
        if len(real) >= 2:
            candidates.add(name)
    return candidates


def build_entity_allowlist(
    verified_claims: list[dict],
    timeline_beats: list[dict],
) -> set[str]:
    """Build the set of named humans that are allowed in the script.

    Sources: claim named_entities, claim_text, timeline beat pov & event.
    """
    allowed: set[str] = set()

    for claim in verified_claims:
        # From explicit named_entities field
        for ent in claim.get("named_entities", []):
            allowed.add(ent)
        # From claim text
        allowed |= extract_named_humans(claim.get("claim_text", ""))

    for beat in timeline_beats:
        pov = beat.get("pov", "")
        if pov:
            allowed.add(pov)
        allowed |= extract_named_humans(beat.get("event", ""))

    return allowed


# ────────────────────────────────────────────────────────────────────────────
# Validator functions
# ────────────────────────────────────────────────────────────────────────────


def validate_entity_provenance(
    script: str,
    verified_claims: list[dict],
    timeline_beats: list[dict],
) -> list[ValidationIssue]:
    """Flag named humans in the script that do NOT appear in claims or beats."""
    allowlist = build_entity_allowlist(verified_claims, timeline_beats)
    script_names = extract_named_humans(script)

    issues: list[ValidationIssue] = []
    for name in sorted(script_names):
        # Check if this name (or a substring) is in the allowlist
        found = any(
            name in allowed or allowed in name
            for allowed in allowlist
        )
        if not found:
            issues.append(ValidationIssue(
                code="ENTITY_NOT_IN_CLAIMS",
                severity="hard",
                message=f"Named human '{name}' appears in script but not in verified claims or timeline beats.",
            ))
    return issues


def validate_word_count(
    script: str, min_words: int, max_words: int,
) -> list[ValidationIssue]:
    """Enforce strict word-count bounds."""
    wc = len(script.split())
    issues: list[ValidationIssue] = []
    if wc < min_words:
        issues.append(ValidationIssue(
            code="WORD_COUNT_UNDER",
            severity="hard",
            message=f"Script is {wc} words, below minimum {min_words}.",
        ))
    if wc > max_words:
        issues.append(ValidationIssue(
            code="WORD_COUNT_OVER",
            severity="hard",
            message=f"Script is {wc} words, above maximum {max_words}.",
        ))
    return issues


def validate_rehook_cadence(
    script: str, rehook_words: int, tolerance: float = 1.25,
) -> list[ValidationIssue]:
    """Flag stretches of text that exceed `rehook_words * tolerance` without a
    re-hook marker (section break, question mark, or dramatic dash).
    """
    # Split on section markers
    sections = _SECTION_MARKER_RE.split(script)
    max_gap = int(rehook_words * tolerance)
    issues: list[ValidationIssue] = []

    # Re-hook signals: question marks, em-dashes, ellipses
    rehook_signals = re.compile(r"[?]|—|\.{3}")

    for i, section in enumerate(sections):
        words = section.split()
        last_signal = 0
        for j, word in enumerate(words):
            if rehook_signals.search(word):
                last_signal = j
            elif j - last_signal > max_gap:
                issues.append(ValidationIssue(
                    code="REHOOK_GAP",
                    severity="soft",
                    message=(
                        f"~{j - last_signal} words without a re-hook signal "
                        f"(max allowed ~{max_gap}) in section {i}."
                    ),
                    location=f"section_{i}",
                ))
                last_signal = j  # reset to avoid duplicate flags
    return issues


def validate_open_loops(
    outline_sections: list[dict],
) -> list[ValidationIssue]:
    """Ensure every open loop resolves or escalates within 2 sections."""
    open_loops: dict[str, int] = {}  # loop_text → section_index where opened
    issues: list[ValidationIssue] = []

    for idx, section in enumerate(outline_sections):
        # Loops opened in this section
        for loop in section.get("open_loops", []):
            normalised = loop.strip().lower()
            if normalised and normalised not in open_loops:
                open_loops[normalised] = idx

        # Loops resolved by key beats or re-hooks
        resolved_text = " ".join(
            section.get("key_beats", []) + section.get("re_hooks", [])
        ).lower()
        to_remove = []
        for loop_text, opened_at in open_loops.items():
            if loop_text in resolved_text:
                to_remove.append(loop_text)
        for lt in to_remove:
            del open_loops[lt]

    # Check remaining open loops — flag if opened > 2 sections before end
    total_sections = len(outline_sections)
    for loop_text, opened_at in open_loops.items():
        if total_sections - opened_at > 2:
            issues.append(ValidationIssue(
                code="OPEN_LOOP_UNRESOLVED",
                severity="soft",
                message=f"Open loop '{loop_text[:60]}…' opened at section {opened_at} never resolved.",
                location=f"section_{opened_at}",
            ))
    return issues


def validate_essay_blocks(
    script: str,
    block_threshold: int = 60,
) -> list[ValidationIssue]:
    """Flag blocks of `block_threshold`+ words with zero named humans, zero
    sensory cues, and zero decision/action verbs.
    """
    # Sensory cue patterns
    sensory_re = re.compile(
        r"\b(smell|sound|hear|see|feel|touch|taste|warm|cold|dark|light|"
        r"bright|dim|loud|quiet|scream|whisper|creak|crack|smoke|dust|"
        r"sweat|blood|rain|wind|thunder|fire|shadow|echo|rumble|flash|"
        r"glint|roar|hiss|clatter|thud|boom|stench|aroma|humid|frozen|"
        r"scorching|damp|wet|dry|rough|smooth|sharp|dull|bitter|sweet)\b",
        re.IGNORECASE,
    )

    # Decision/action verbs
    decision_re = re.compile(
        r"\b(decided|chose|ordered|commanded|refused|agreed|demanded|"
        r"insisted|risked|gambled|surrendered|retreated|advanced|charged|"
        r"fired|pulled|pushed|grabbed|seized|ran|fled|hid|fought|"
        r"negotiated|signed|wrote|sent|built|destroyed|launched|"
        r"abandoned|betrayed|defied|challenged|confronted|escaped)\b",
        re.IGNORECASE,
    )

    issues: list[ValidationIssue] = []
    # Split into paragraphs
    paragraphs = re.split(r"\n\s*\n|---\s*\[.*?\]\s*---", script)

    for i, para in enumerate(paragraphs):
        words = para.split()
        if len(words) < block_threshold:
            continue

        has_name = bool(extract_named_humans(para))
        has_sensory = bool(sensory_re.search(para))
        has_decision = bool(decision_re.search(para))

        if not has_name and not has_sensory and not has_decision:
            snippet = " ".join(words[:12]) + "…"
            issues.append(ValidationIssue(
                code="ESSAY_BLOCK",
                severity="hard",
                message=(
                    f"Block of {len(words)} words with no named human, no sensory "
                    f"detail, and no decision verb: \"{snippet}\""
                ),
                location=f"paragraph_{i}",
            ))
    return issues


def validate_tension_escalation(
    beats: list[dict],
    max_non_increasing: int = 2,
    spike_after_dip: int = 2,
) -> list[ValidationIssue]:
    """Enforce mathematical escalation on timeline tension_level.

    Rules:
    - Allow at most `max_non_increasing` non-increasing transitions total.
    - Any dip must be followed by a +`spike_after_dip` spike within 1 beat.
    """
    issues: list[ValidationIssue] = []
    if len(beats) < 2:
        return issues

    levels = [b.get("tension_level", 0) for b in beats]
    non_inc_count = 0

    for i in range(1, len(levels)):
        if levels[i] <= levels[i - 1]:
            non_inc_count += 1
            if non_inc_count > max_non_increasing:
                issues.append(ValidationIssue(
                    code="TENSION_TOO_MANY_DIPS",
                    severity="hard",
                    message=(
                        f"Beat {i}: tension {levels[i - 1]}→{levels[i]} is the "
                        f"{non_inc_count}th non-increasing transition (max {max_non_increasing})."
                    ),
                    location=f"beat_{i}",
                ))

            # Check spike recovery
            if levels[i] < levels[i - 1]:
                next_level = levels[i + 1] if i + 1 < len(levels) else None
                if next_level is None or next_level < levels[i] + spike_after_dip:
                    actual_spike = (next_level - levels[i]) if next_level is not None else 0
                    issues.append(ValidationIssue(
                        code="TENSION_NO_SPIKE_AFTER_DIP",
                        severity="soft",
                        message=(
                            f"Beat {i}: tension dipped {levels[i - 1]}→{levels[i]} "
                            f"but next beat only recovers by +{actual_spike} "
                            f"(need +{spike_after_dip})."
                        ),
                        location=f"beat_{i}",
                    ))
    return issues


def validate_twist_distribution(
    beats: list[dict],
    min_act2_fraction: float = 0.50,
) -> list[ValidationIssue]:
    """Ensure at least `min_act2_fraction` of is_twist beats fall in Act 2 range.

    Act 2 is defined as the middle 40% of beats (indices 30%-70%).
    """
    issues: list[ValidationIssue] = []
    if len(beats) < 4:
        return issues

    n = len(beats)
    act2_start = int(n * 0.3)
    act2_end = int(n * 0.7)

    twist_indices = [i for i, b in enumerate(beats) if b.get("is_twist", False)]
    if not twist_indices:
        issues.append(ValidationIssue(
            code="NO_TWISTS",
            severity="hard",
            message="Timeline has zero twist beats.",
        ))
        return issues

    act2_twists = [i for i in twist_indices if act2_start <= i <= act2_end]
    fraction = len(act2_twists) / len(twist_indices)

    if fraction < min_act2_fraction:
        issues.append(ValidationIssue(
            code="TWIST_DISTRIBUTION_SKEWED",
            severity="soft",
            message=(
                f"Only {len(act2_twists)}/{len(twist_indices)} twist beats "
                f"({fraction:.0%}) fall in Act 2 range (need ≥{min_act2_fraction:.0%})."
            ),
        ))
    return issues


def validate_outline_word_sum(
    sections: list[dict],
    target_words: int,
    tolerance: float = 0.10,
) -> list[ValidationIssue]:
    """Check that outline section word counts sum to approximately target_words."""
    issues: list[ValidationIssue] = []
    total = sum(s.get("target_word_count", 0) for s in sections)
    low = int(target_words * (1 - tolerance))
    high = int(target_words * (1 + tolerance))

    if total < low or total > high:
        issues.append(ValidationIssue(
            code="OUTLINE_WORD_SUM_MISMATCH",
            severity="soft",
            message=f"Outline sections sum to {total} words, target is {target_words} (±{tolerance:.0%}).",
        ))
    return issues


# ────────────────────────────────────────────────────────────────────────────
# Trace-tag utilities for Fact-Tighten pass
# ────────────────────────────────────────────────────────────────────────────

_TRACE_TAG_RE = re.compile(r"\s*\[Beat B\d+\s*\|\s*Claims [C\d,\s]+\]")


def strip_trace_tags(script: str) -> str:
    """Remove [Beat Bxx | Claims Cxxx,Cyyy] tags from the final script."""
    return _TRACE_TAG_RE.sub("", script)


def extract_trace_tags(script: str) -> list[dict[str, str | list[str]]]:
    """Extract all trace tags from a script for audit purposes."""
    tags: list[dict[str, str | list[str]]] = []
    for match in re.finditer(r"\[Beat (B\d+)\s*\|\s*Claims ([C\d,\s]+)\]", script):
        beat = match.group(1)
        claims = [c.strip() for c in match.group(2).split(",")]
        tags.append({"beat": beat, "claims": claims})
    return tags


# ────────────────────────────────────────────────────────────────────────────
# Retention-pass entity guard
# ────────────────────────────────────────────────────────────────────────────


def validate_retention_no_new_entities(
    original_script: str,
    revised_script: str,
) -> list[ValidationIssue]:
    """Ensure the retention pass did not introduce new named humans."""
    original_names = extract_named_humans(original_script)
    revised_names = extract_named_humans(revised_script)
    new_names = revised_names - original_names

    issues: list[ValidationIssue] = []
    for name in sorted(new_names):
        issues.append(ValidationIssue(
            code="RETENTION_NEW_ENTITY",
            severity="hard",
            message=f"Retention pass introduced new named human '{name}' not in original script.",
        ))
    return issues


# ────────────────────────────────────────────────────────────────────────────
# Full pre-script validation gate
# ────────────────────────────────────────────────────────────────────────────


def run_pre_script_validation(
    outline_sections: list[dict],
    timeline_beats: list[dict],
    verified_claims: list[dict],
    target_words: int,
    rehook_words: int,
) -> ValidationReport:
    """Run all pre-script-generation guardrails.

    This is the validation gate that fires BEFORE script_generation.
    """
    report = ValidationReport()

    # 1. Outline word-count sum
    for issue in validate_outline_word_sum(outline_sections, target_words):
        report.add(issue.code, issue.message, issue.severity, issue.location)

    # 2. Open-loop resolution
    for issue in validate_open_loops(outline_sections):
        report.add(issue.code, issue.message, issue.severity, issue.location)

    # 3. Tension escalation
    for issue in validate_tension_escalation(timeline_beats):
        report.add(issue.code, issue.message, issue.severity, issue.location)

    # 4. Twist distribution
    for issue in validate_twist_distribution(timeline_beats):
        report.add(issue.code, issue.message, issue.severity, issue.location)

    return report


def run_post_script_validation(
    script: str,
    verified_claims: list[dict],
    timeline_beats: list[dict],
    min_words: int,
    max_words: int,
    rehook_words: int,
) -> ValidationReport:
    """Run all post-script-generation guardrails.

    This fires after the draft or fact-tighten pass.
    """
    report = ValidationReport()

    # 1. Word count
    for issue in validate_word_count(script, min_words, max_words):
        report.add(issue.code, issue.message, issue.severity, issue.location)

    # 2. Entity provenance
    for issue in validate_entity_provenance(script, verified_claims, timeline_beats):
        report.add(issue.code, issue.message, issue.severity, issue.location)

    # 3. Rehook cadence
    for issue in validate_rehook_cadence(script, rehook_words):
        report.add(issue.code, issue.message, issue.severity, issue.location)

    # 4. Essay blocks
    for issue in validate_essay_blocks(script):
        report.add(issue.code, issue.message, issue.severity, issue.location)

    return report
