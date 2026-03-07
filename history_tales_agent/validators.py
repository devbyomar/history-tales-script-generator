"""Pydantic schemas for structured pipeline artifacts and deterministic validators.

Every JSON artifact returned by the LLM is parsed into one of these schemas.
Validator functions enforce hard constraints that the LLM cannot be trusted to
guarantee — word count, named-entity provenance, rehook cadence, open-loop
resolution, essay-block detection, tension escalation, twist distribution,
sentence-length ceiling, and near-identical fact repetition.
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

# Words that commonly start sentences and get capitalised but are NOT names.
# Used as the FIRST word filter — if a "name" begins with one of these,
# it's almost certainly not a real human name.
_SENTENCE_START_WORDS = {
    "after", "before", "during", "between", "across", "against",
    "around", "behind", "below", "beneath", "beside", "beyond",
    "despite", "except", "following", "inside", "outside", "since",
    "through", "throughout", "toward", "towards", "under", "until",
    "upon", "within", "without", "along", "among", "meanwhile",
    "however", "therefore", "furthermore", "moreover", "nevertheless",
    "nonetheless", "otherwise", "still", "then", "thus", "yet",
    "both", "each", "every", "either", "neither", "several",
    "many", "most", "some", "such", "like", "over", "only",
}

# Phrases that LOOK like named humans to the regex but are NOT (Change 20)
_FALSE_POSITIVE_NAMES = {
    # Organisations / alliances
    "Red Cross", "Iron Cross", "Iron Curtain", "Cold War",
    "Second World War", "First World War", "World War",
    "Third Reich", "Soviet Union", "United States", "United Kingdom",
    "United Nations", "Nazi Germany", "Great Britain", "South Africa",
    "North Africa", "East Berlin", "West Berlin", "East Germany",
    "West Germany", "North Korea", "South Korea",
    "Central Intelligence Agency", "Secret Intelligence Service",
    "Special Operations Executive", "Royal Air Force",
    "Secret Service",

    # Places / geographic features
    "Pearl Harbor", "Monte Cassino", "Buenos Aires", "Los Alamos",
    "San Francisco", "New York", "Cape Town", "Camp David",
    "Las Vegas", "Los Angeles", "San Diego", "San Antonio",
    "El Paso", "El Alamein", "Monte Carlo", "Rio de Janeiro",
    "Pas de Calais", "Sierra Nevada", "Lake Geneva",
    "The Sierra Nevada", "The Middle East",
    "Northern France", "Southern France", "Western Europe",
    "Eastern Europe", "Northern Europe", "Southern Europe",
    "Latin America", "Central America", "South America",
    "North America", "Southeast Asia", "East Asia",
    "Middle East", "Near East", "Far East",

    # Temporal phrases that start with capitalised words
    "After Appell", "Before Dawn", "During Winter",
    "During the Second World War", "During the First World War",
    "In April", "In March", "In June", "In July", "In August",
    "In September", "In October", "In November", "In December",
    "In January", "In February", "In May", "By Morning", "By Evening",
    "By Night", "Next Morning", "That Evening", "That Night",
    "Early Morning", "Late Evening",
}

# First words that signal the phrase is NOT a human name.
# Includes military/institutional prefixes, geographic prefixes, etc.
_NON_HUMAN_FIRST_WORDS = {
    # Military / operational
    "operation", "army", "battle", "camp", "fort", "fortress",
    "regiment", "division", "brigade", "squadron", "battalion",
    "corps", "fleet", "convoy", "task",
    # Geographic
    "cape", "lake", "mount", "sierra", "rio", "port",
    "bay", "gulf", "strait", "channel", "isle",
    "northern", "southern", "eastern", "western",
    "north", "south", "east", "west", "central",
    "atlantic", "pacific", "baltic", "arctic", "antarctic",
    "mediterranean", "caribbean", "adriatic", "aegean",
    "middle", "black", "red", "white", "dead",
    # Foreign geographic words common in history scripts
    "puente", "plaza", "palacio", "cerro", "campo",
    "monte", "ponte", "piazza", "platz", "schloss",
    "tempelhof", "bletchley",
    # Institutional / governmental
    "foreign", "war", "state", "high", "supreme",
    "royal", "imperial", "national", "federal", "special",
    "central", "allied",
}

# Last words that signal the phrase is NOT a human name.
# Places, organisations, and features typically end with these.
_NON_HUMAN_LAST_WORDS = {
    # Geographic features
    "sea", "ocean", "wall", "front", "theater", "theatre",
    "channel", "harbor", "harbour", "strait", "bay", "gulf",
    "mountains", "hills", "plains", "desert",
    "peninsula", "island", "islands", "lake", "river", "valley",
    "coast", "ridge", "pass", "basin", "plateau", "canal",
    "park", "forest", "creek", "falls", "springs",
    # Structures / fortifications
    "line", "gate", "bridge", "tower", "bunker", "barracks",
    "machine", "factory", "yard", "dock", "airfield",
    "airport", "station", "terminal", "port", "square",
    "avenue", "street", "road", "highway", "boulevard",
    # Institutional / military
    "office", "agency", "force", "service", "command",
    "staff", "department", "bureau", "council", "committee",
    "headquarters", "group", "corps", "fleet", "division",
    "brigade", "regiment", "squadron", "battalion",
    # Abstractions / events
    "plan", "pact", "treaty", "accord", "act",
    "program", "programme", "project", "initiative",
    "house", "palace", "castle", "church",
    "conference", "congress", "parliament",
    "overlord", "barbarossa", "citadel", "dragoon",
    # Countries / regions (when used as last word)
    "france", "germany", "europe", "america", "asia", "africa",
    "union", "states", "kingdom", "nations", "reich",
    # Number words (e.g. "Serpukhov Fifteen", "Stalag Three")
    "one", "two", "three", "four", "five", "six", "seven",
    "eight", "nine", "ten", "eleven", "twelve", "thirteen",
    "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
    "nineteen", "twenty",
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

    Multi-layer filtering to reduce false positives:
      1. Exact match against _FALSE_POSITIVE_NAMES
      2. First-word check against _SENTENCE_START_WORDS
      3. First-word check against _NON_HUMAN_FIRST_WORDS
      4. Last-word check against _NON_HUMAN_LAST_WORDS
      5. Title-word density check (must have ≥2 real words)
    """
    # Remove section markers
    cleaned = _SECTION_MARKER_RE.sub("", text)
    # Remove quoted strings (which may contain titles)
    cleaned = re.sub(r'"[^"]*"', "", cleaned)

    candidates: set[str] = set()
    for match in _NAME_PATTERN.finditer(cleaned):
        name = match.group(1).strip()
        tokens = name.split()

        # Layer 1: exact match against known false positives
        if name in _FALSE_POSITIVE_NAMES:
            continue

        # Layer 2: sentence-start words (e.g. "During", "However")
        first_word = tokens[0].lower()
        if first_word in _SENTENCE_START_WORDS:
            continue

        # Layer 3: non-human first words (e.g. "Operation", "Camp", "Lake")
        if first_word in _NON_HUMAN_FIRST_WORDS:
            continue

        # Layer 3b: "The X …" — if the second word is a non-human first word,
        # filter it out (e.g. "The Atlantic Wall", "The Sierra Nevada",
        # "The Middle East", "The Pacific Theater")
        if first_word == "the" and len(tokens) >= 2:
            second_word = tokens[1].lower()
            if second_word in _NON_HUMAN_FIRST_WORDS:
                continue

        # Layer 4: non-human last words (e.g. "Sea", "Force", "Office")
        last_word = tokens[-1].lower()
        if last_word in _NON_HUMAN_LAST_WORDS:
            continue

        # Layer 5: must have at least 2 real capitalised words
        real = [t for t in tokens if t.lower() not in _TITLE_WORDS and len(t) > 1]
        if len(real) < 2:
            continue

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


def validate_sentence_length(
    script: str,
    hard_ceiling: int = 25,
    avg_ceiling: int = 20,
    max_flagged: int = 10,
) -> list[ValidationIssue]:
    """Flag sentences that exceed `hard_ceiling` words.

    Also flags if the overall average sentence length exceeds `avg_ceiling`.
    Reports at most `max_flagged` individual sentences to keep logs concise.
    """
    # Split into sentences using punctuation boundaries
    sentences = re.split(r'(?<=[.!?])\s+', script)
    issues: list[ValidationIssue] = []
    word_counts: list[int] = []
    flagged = 0

    for sent in sentences:
        words = sent.split()
        wc = len(words)
        if wc < 3:
            # Skip fragments (e.g. "He ran." after split)
            continue
        word_counts.append(wc)
        if wc > hard_ceiling and flagged < max_flagged:
            snippet = " ".join(words[:10]) + ("…" if wc > 10 else "")
            issues.append(ValidationIssue(
                code="SENTENCE_OVER_LIMIT",
                severity="soft",
                message=(
                    f"Sentence is {wc} words (ceiling {hard_ceiling}): \"{snippet}\""
                ),
            ))
            flagged += 1

    if word_counts:
        avg = sum(word_counts) / len(word_counts)
        if avg > avg_ceiling:
            issues.append(ValidationIssue(
                code="SENTENCE_AVG_HIGH",
                severity="soft",
                message=(
                    f"Average sentence length is {avg:.1f} words "
                    f"(target ≤{avg_ceiling}). Script has {len(word_counts)} sentences."
                ),
            ))

    return issues


def validate_fact_repetition(
    script: str,
    ngram_size: int = 4,
    max_repeats: int = 2,
    max_flagged: int = 8,
) -> list[ValidationIssue]:
    """Flag near-identical fact restatements using n-gram overlap.

    Scans for repeated 4-grams (ignoring very common words) that appear
    more than `max_repeats` times, which signals the same fact phrase
    being restated in near-identical language.
    """
    # Common stopwords to skip when building n-grams
    _stopwords = {
        "the", "a", "an", "of", "and", "in", "at", "on", "to", "for",
        "by", "is", "was", "are", "were", "has", "had", "have", "will",
        "would", "but", "or", "not", "it", "he", "she", "they", "we",
        "his", "her", "its", "their", "our", "this", "that", "from",
        "with", "into", "be", "been", "as", "which", "who", "whom",
    }

    words = [w.lower().strip(".,;:!?\"'()[]—–-") for w in script.split()]
    content_words = [w for w in words if w and w not in _stopwords and len(w) > 2]

    if len(content_words) < ngram_size:
        return []

    # Build n-gram counts
    ngram_counts: dict[tuple[str, ...], int] = {}
    for i in range(len(content_words) - ngram_size + 1):
        gram = tuple(content_words[i:i + ngram_size])
        ngram_counts[gram] = ngram_counts.get(gram, 0) + 1

    issues: list[ValidationIssue] = []
    flagged = 0
    for gram, count in sorted(ngram_counts.items(), key=lambda x: -x[1]):
        if count <= max_repeats:
            break
        if flagged >= max_flagged:
            break
        phrase = " ".join(gram)
        issues.append(ValidationIssue(
            code="FACT_REPETITION",
            severity="soft",
            message=(
                f"Phrase '{phrase}' appears {count} times "
                f"(max {max_repeats}). Check for near-identical restatements."
            ),
        ))
        flagged += 1

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
# Exposition-density validator (Change 21)
# ────────────────────────────────────────────────────────────────────────────


def validate_exposition_density(
    script: str,
    max_consecutive_exposition: int = 3,
    word_threshold: int = 45,
) -> list[ValidationIssue]:
    """Flag stretches of consecutive paragraphs that are pure exposition.

    An exposition paragraph = no named human, no decision/action verb, and
    no sensory cue — i.e. pure analytical or contextual text.  More than
    `max_consecutive_exposition` such paragraphs in a row signals essay drift.
    """
    # Reuse patterns from validate_essay_blocks
    sensory_re = re.compile(
        r"\b(smell|sound|hear|see|feel|touch|taste|warm|cold|dark|light|"
        r"bright|dim|loud|quiet|scream|whisper|creak|crack|smoke|dust|"
        r"sweat|blood|rain|wind|thunder|fire|shadow|echo|rumble|flash|"
        r"glint|roar|hiss|clatter|thud|boom|stench|aroma|humid|frozen|"
        r"scorching|damp|wet|dry|rough|smooth|sharp|dull|bitter|sweet)\b",
        re.IGNORECASE,
    )
    decision_re = re.compile(
        r"\b(decided|chose|ordered|commanded|refused|agreed|demanded|"
        r"insisted|risked|gambled|surrendered|retreated|advanced|charged|"
        r"fired|pulled|pushed|grabbed|seized|ran|fled|hid|fought|"
        r"negotiated|signed|wrote|sent|built|destroyed|launched|"
        r"abandoned|betrayed|defied|challenged|confronted|escaped)\b",
        re.IGNORECASE,
    )

    paragraphs = re.split(r"\n\s*\n", script)
    issues: list[ValidationIssue] = []
    consecutive = 0
    streak_start = 0

    for i, para in enumerate(paragraphs):
        words = para.split()
        if len(words) < word_threshold:
            consecutive = 0
            continue

        has_name = bool(extract_named_humans(para))
        has_sensory = bool(sensory_re.search(para))
        has_decision = bool(decision_re.search(para))

        if not has_name and not has_sensory and not has_decision:
            if consecutive == 0:
                streak_start = i
            consecutive += 1
        else:
            consecutive = 0

        if consecutive > max_consecutive_exposition:
            snippet = " ".join(words[:12]) + "…"
            issues.append(ValidationIssue(
                code="EXPOSITION_DRIFT",
                severity="soft",
                message=(
                    f"{consecutive} consecutive exposition paragraphs starting at "
                    f"paragraph {streak_start}: \"{snippet}\". "
                    f"Break with a named actor, sensory detail, or decision."
                ),
                location=f"paragraph_{streak_start}",
            ))
            consecutive = 0  # Reset to avoid duplicate flags

    return issues


# ────────────────────────────────────────────────────────────────────────────
# Anti-poetic pattern validator
# ────────────────────────────────────────────────────────────────────────────

# Pre-compiled patterns for the 7 banned anti-poetic constructions.
# Each pattern captures the offending phrase for reporting.

# 1. "The [noun] of [abstract noun]" — e.g. "The architecture of betrayal"
_ANTIPOETIC_NOUN_OF_ABSTRACT = re.compile(
    r"\bThe\s+[a-z]+\s+of\s+"
    r"(?:betrayal|deception|fear|power|silence|control|doubt|loss|hope|"
    r"despair|freedom|survival|resistance|courage|defiance|ambition|"
    r"reckoning|fate|destruction|redemption|liberation|oppression|"
    r"tyranny|justice|vengeance|grief|terror|dread|fury|rage|"
    r"consequence|collapse|decay|corruption|glory|triumph|tragedy|"
    r"obedience|complicity|memory|forgetting|absolution|mercy|"
    r"dominance|submission|inevitability|finality|mortality)\b",
    re.IGNORECASE,
)

# 2. "It was not X — it was Y" / "This was not X — it was Y" rhetorical pivots
_ANTIPOETIC_NOT_X_WAS_Y = re.compile(
    r"\b(?:It|This|That|He|She)\s+was\s+not\s+.{3,40}\s*[—–-]\s*it\s+was\s+",
    re.IGNORECASE,
)

# 3. Noun-as-verb poetic formulations — abstract nouns used as verbs
_ANTIPOETIC_NOUN_AS_VERB = re.compile(
    r"\b(?:History|Time|Silence|Fear|War|Peace|Death|Truth|Power|Fate|"
    r"Memory|Hope|Darkness|Light|Chaos)\s+"
    r"(?:telescoped|whispered|screamed|demanded|beckoned|swallowed|"
    r"consumed|devoured|shattered|crumbled|rippled|echoed|unraveled|"
    r"collapsed|fractured|eroded|dissolved|crystallized|converged|"
    r"spiraled|cascaded|reverberated|pulsed)\b",
    re.IGNORECASE,
)

# 4. Stacked prepositional metaphors — 3+ prepositional phrases in a row
_ANTIPOETIC_STACKED_PREPS = re.compile(
    r"(?:(?:beneath|above|beyond|within|behind|across|through|between|"
    r"among|against|upon|over|under|inside|outside|amid|amidst|along|"
    r"around|before|after|towards?|into|onto|past|without)\s+(?:the\s+)?"
    r"[a-z]+(?:\s+[a-z]+)?(?:\s*,\s*|\s+)){2,}"
    r"(?:beneath|above|beyond|within|behind|across|through|between|"
    r"among|against|upon|over|under|inside|outside|amid|amidst|along|"
    r"around|before|after|towards?|into|onto|past|without)\s+",
    re.IGNORECASE,
)

# 5. Decorative personification of abstractions
_ANTIPOETIC_PERSONIFICATION = re.compile(
    r"\b(?:Silence|Fear|Death|Time|History|War|Peace|Truth|Darkness|"
    r"Doubt|Hope|Memory|Grief|Shame|Guilt|Rage|Fury|Despair|"
    r"Chaos|Fate|Justice|Freedom|Power)\s+"
    r"(?:carried|held|whispered|spoke|watched|waited|crept|settled|"
    r"lingered|descended|hung|pressed|wrapped|consumed|devoured|"
    r"gripped|seized|embraced|clung|weighed|bore|stretched|loomed|"
    r"arrived|moved|stood|sat)\b",
    re.IGNORECASE,
)

# 6. Clause-chain sentences — 3+ commas building to a dramatic landing
#    Heuristic: a sentence with 4+ commas and 25+ words
_ANTIPOETIC_CLAUSE_CHAIN_COMMA_THRESHOLD = 4
_ANTIPOETIC_CLAUSE_CHAIN_WORD_THRESHOLD = 25

# 7. Poetic thesis closings
_ANTIPOETIC_POETIC_CLOSING = re.compile(
    r"(?:And\s+in\s+the\s+silence\s+that\s+followed|"
    r"Perhaps\s+the\s+(?:true\s+)?lesson\s+(?:is|was)|"
    r"History\s+would\s+(?:later\s+)?remember|"
    r"In\s+the\s+end\s*,?\s+(?:it\s+was|what\s+remained)|"
    r"courage\s+is\s+not\s+the\s+absence\s+of\s+fear|"
    r"And\s+so\s*,?\s+the\s+world\s+(?:learned|discovered|understood)|"
    r"what\s+(?:remained|endured|lingered)\s+was\s+(?:not\s+)?the)",
    re.IGNORECASE,
)


def validate_anti_poetic_patterns(
    script: str,
    max_flagged_per_pattern: int = 5,
) -> list[ValidationIssue]:
    """Scan script for the 7 banned anti-poetic patterns.

    Returns a list of ValidationIssues (severity="soft") for each violation.
    Reports at most `max_flagged_per_pattern` instances per pattern type
    to keep logs concise.
    """
    issues: list[ValidationIssue] = []

    def _flag(code: str, pattern_name: str, matches: list[str]) -> None:
        for match_text in matches[:max_flagged_per_pattern]:
            snippet = match_text.strip()[:80]
            issues.append(ValidationIssue(
                code=code,
                severity="soft",
                message=f"{pattern_name}: \"{snippet}\"",
            ))

    # 1. "The [noun] of [abstract noun]"
    matches_1 = _ANTIPOETIC_NOUN_OF_ABSTRACT.findall(script)
    # findall returns strings (the full match)
    matches_1_full = [m.group() for m in _ANTIPOETIC_NOUN_OF_ABSTRACT.finditer(script)]
    _flag("ANTIPOETIC_NOUN_OF_ABSTRACT", "The [noun] of [abstract noun]", matches_1_full)

    # 2. "It was not X — it was Y"
    matches_2 = [m.group() for m in _ANTIPOETIC_NOT_X_WAS_Y.finditer(script)]
    _flag("ANTIPOETIC_NOT_X_WAS_Y", "It was not X — it was Y pivot", matches_2)

    # 3. Noun-as-verb
    matches_3 = [m.group() for m in _ANTIPOETIC_NOUN_AS_VERB.finditer(script)]
    _flag("ANTIPOETIC_NOUN_AS_VERB", "Noun-as-verb poetic formulation", matches_3)

    # 4. Stacked prepositional metaphors
    matches_4 = [m.group() for m in _ANTIPOETIC_STACKED_PREPS.finditer(script)]
    _flag("ANTIPOETIC_STACKED_PREPS", "Stacked prepositional metaphors", matches_4)

    # 5. Decorative personification
    matches_5 = [m.group() for m in _ANTIPOETIC_PERSONIFICATION.finditer(script)]
    _flag("ANTIPOETIC_PERSONIFICATION", "Decorative personification of abstraction", matches_5)

    # 6. Clause-chain sentences (3+ commas, 30+ words)
    sentences = re.split(r'(?<=[.!?])\s+', script)
    clause_chain_count = 0
    for sent in sentences:
        comma_count = sent.count(",")
        word_count = len(sent.split())
        if (comma_count >= _ANTIPOETIC_CLAUSE_CHAIN_COMMA_THRESHOLD
                and word_count >= _ANTIPOETIC_CLAUSE_CHAIN_WORD_THRESHOLD):
            if clause_chain_count < max_flagged_per_pattern:
                snippet = " ".join(sent.split()[:12]) + "…"
                issues.append(ValidationIssue(
                    code="ANTIPOETIC_CLAUSE_CHAIN",
                    severity="soft",
                    message=(
                        f"Clause-chain sentence ({comma_count} commas, "
                        f"{word_count} words): \"{snippet}\""
                    ),
                ))
            clause_chain_count += 1

    # 7. Poetic thesis closings
    matches_7 = [m.group() for m in _ANTIPOETIC_POETIC_CLOSING.finditer(script)]
    _flag("ANTIPOETIC_POETIC_CLOSING", "Poetic thesis closing", matches_7)

    # Summary issue if total violations > 0
    total = len(issues)
    if total > 0:
        issues.insert(0, ValidationIssue(
            code="ANTIPOETIC_SUMMARY",
            severity="soft",
            message=(
                f"Anti-poetic scan found {total} violation(s) across 7 pattern "
                f"categories. Each should be rewritten in plain conversational English."
            ),
        ))

    return issues


# ────────────────────────────────────────────────────────────────────────────
# Timeline structural validator (Change 7)
# ────────────────────────────────────────────────────────────────────────────


def validate_timeline_structure(
    beats: list[dict],
    min_beats: int = 4,
    min_twists: int = 1,
) -> list[ValidationIssue]:
    """Flag structurally empty or weak timelines.

    A timeline with zero beats or zero twists means the evidence base was
    too weak to construct a real dramatic arc — downstream nodes should not
    proceed as if nothing happened.
    """
    issues: list[ValidationIssue] = []

    if len(beats) == 0:
        issues.append(ValidationIssue(
            code="TIMELINE_EMPTY",
            severity="hard",
            message=(
                "Timeline has zero beats. Evidence base may be insufficient "
                "for a micro-incident script. Consider a broader framing or "
                "composite reconstruction mode."
            ),
        ))
        return issues

    if len(beats) < min_beats:
        issues.append(ValidationIssue(
            code="TIMELINE_TOO_SHORT",
            severity="soft",
            message=(
                f"Timeline has only {len(beats)} beats (minimum {min_beats}). "
                f"The dramatic arc may be too thin."
            ),
        ))

    twist_count = sum(1 for b in beats if b.get("is_twist", False))
    if twist_count < min_twists:
        issues.append(ValidationIssue(
            code="TIMELINE_NO_TWISTS",
            severity="hard",
            message=(
                f"Timeline has {twist_count} twist beats (minimum {min_twists}). "
                f"The story lacks dramatic turning points."
            ),
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

    # 5. Timeline structural integrity (Change 7)
    for issue in validate_timeline_structure(timeline_beats):
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

    # 5. Sentence length ceiling
    for issue in validate_sentence_length(script):
        report.add(issue.code, issue.message, issue.severity, issue.location)

    # 6. Fact repetition
    for issue in validate_fact_repetition(script):
        report.add(issue.code, issue.message, issue.severity, issue.location)

    # 7. Exposition drift (Change 21)
    for issue in validate_exposition_density(script):
        report.add(issue.code, issue.message, issue.severity, issue.location)

    # 8. Anti-poetic patterns
    for issue in validate_anti_poetic_patterns(script):
        report.add(issue.code, issue.message, issue.severity, issue.location)

    return report
