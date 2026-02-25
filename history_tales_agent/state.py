"""Pydantic state schema for the LangGraph agent pipeline."""

from __future__ import annotations

from typing import Any, Optional, TypedDict

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class TopicCandidate(BaseModel):
    """A single topic candidate produced by the discovery node."""

    title: str
    one_sentence_hook: str
    era: str
    geo: str
    core_pov: str
    timeline_window: str
    twist_points: list[str] = Field(default_factory=list, min_length=3, max_length=5)
    what_people_get_wrong: str = ""
    format_tag: str = ""
    likely_sources: list[str] = Field(default_factory=list)
    # Scoring (filled by TopicScoringNode)
    score: float = 0.0
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    runtime_fit_multiplier: float = 1.0


class SourceEntry(BaseModel):
    """A single source used in research."""

    name: str
    url: str
    domain: str = ""
    source_type: str = ""  # "Primary" | "Secondary" | "Derived"
    credibility_score: float = 0.0
    is_institutional: bool = False
    notes: str = ""


class Claim(BaseModel):
    """A single factual claim extracted from research."""

    claim_id: str = ""  # C001, C002, …
    claim_text: str
    source_name: str
    source_url: str
    source_type: str = "Secondary"  # "Primary" | "Secondary" | "Derived"
    confidence: str = "Moderate"  # "High" | "Moderate" | "Contested"
    cross_checked: bool = False
    cross_check_notes: str = ""
    date_anchor: str = ""  # e.g. "1944-06-06" or ""
    named_entities: list[str] = Field(default_factory=list)
    quote_candidate: bool = False
    script_language: str = ""  # safe narration sentence from cross-check


class TimelineBeat(BaseModel):
    """A beat on the narrative timeline."""

    timestamp: str = ""  # e.g. "June 5, 1944, 21:15"
    event: str
    pov: str = ""
    tension_level: int = 0  # 1–10
    is_twist: bool = False
    open_loop: str = ""
    resolves_loop: str = ""


class NarrativeThread(BaseModel):
    """A thread of narrative tension."""

    thread_id: str
    description: str
    pov: str = ""
    opens_at: str = ""
    resolves_at: str = ""
    status: str = "open"  # "open" | "escalated" | "resolved"


class EmotionalDriver(BaseModel):
    """An emotional element extracted from the material."""

    driver_type: str  # "doubt" | "miscalculation" | "moral_tension" | "internal_conflict"
    description: str
    pov: str = ""
    source_reference: str = ""


class RehookPlan(BaseModel):
    """A planned re-hook within a script section."""

    approx_word_index: int = 0
    purpose: str = ""
    line_stub: str = ""


class ScriptSection(BaseModel):
    """A section of the final script outline."""

    section_name: str
    description: str = ""
    target_word_count: int = 0
    minute_range: str = ""  # e.g. "0:00–0:20"
    re_hooks: list[str] = Field(default_factory=list)
    open_loops: list[str] = Field(default_factory=list)
    key_beats: list[str] = Field(default_factory=list)
    rehook_plan: list[RehookPlan] = Field(default_factory=list)


class QCReport(BaseModel):
    """Quality check report."""

    overall_pass: bool = False
    word_count: int = 0
    target_words: int = 0
    word_count_in_range: bool = False
    retention_score: float = 0.0
    emotional_intensity_score: float = 0.0
    sensory_density_score: float = 0.0
    source_count: int = 0
    institutional_source_present: bool = False
    independent_domains: int = 0
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Main agent state
# ---------------------------------------------------------------------------


class AgentState(BaseModel):
    """Complete state passed through the LangGraph pipeline.

    Every node reads from and writes to this state object.
    """

    # ── Input parameters ────────────────────────────────────────────────
    video_length_minutes: int
    era_focus: Optional[str] = None
    geo_focus: Optional[str] = None
    topic_seed: Optional[str] = None
    tone: str = "cinematic-serious"
    sensitivity_level: str = "general audiences"
    nonlinear_open: bool = True
    previous_format_tag: Optional[str] = None
    requested_format_tag: Optional[str] = None

    # ── Narrative lens / geo / mobility (optional expansions) ───────
    narrative_lens: Optional[str | list[str]] = None
    lens_strength: float = 0.6
    geo_scope: Optional[str] = None
    geo_anchor: Optional[str | list[str]] = None
    mobility_mode: Optional[str] = None

    # ── Derived parameters ──────────────────────────────────────────────
    target_words: int = 0
    min_words: int = 0
    max_words: int = 0
    rehook_interval: tuple[int, int] = (60, 90)

    # ── Topic discovery & selection ─────────────────────────────────────
    topic_candidates: list[TopicCandidate] = Field(default_factory=list)
    chosen_topic: Optional[TopicCandidate] = None
    format_tag: str = ""

    # ── Research ────────────────────────────────────────────────────────
    research_corpus: list[dict[str, Any]] = Field(default_factory=list)
    sources_log: list[SourceEntry] = Field(default_factory=list)

    # ── Claims & cross-check ────────────────────────────────────────────
    claims: list[Claim] = Field(default_factory=list)

    # ── Timeline & narrative ────────────────────────────────────────────
    timeline_beats: list[TimelineBeat] = Field(default_factory=list)
    narrative_threads: list[NarrativeThread] = Field(default_factory=list)

    # ── Emotional drivers ───────────────────────────────────────────────
    emotional_drivers: list[EmotionalDriver] = Field(default_factory=list)

    # ── Historiography ──────────────────────────────────────────────────
    consensus_vs_contested: list[dict[str, str]] = Field(default_factory=list)

    # ── Script ──────────────────────────────────────────────────────────
    script_outline: list[ScriptSection] = Field(default_factory=list)
    draft_script: str = ""  # Stage A output (before fact-tighten)
    final_script: str = ""

    # ── Quality ─────────────────────────────────────────────────────────
    qc_report: Optional[QCReport] = None
    emotional_intensity_score: float = 0.0
    sensory_density_score: float = 0.0
    validation_issues: list[str] = Field(default_factory=list)  # from hard guardrails

    # ── Internal tracking ───────────────────────────────────────────────
    current_node: str = ""
    errors: list[str] = Field(default_factory=list)
    iteration_count: int = 0


# ---------------------------------------------------------------------------
# TypedDict state for LangGraph (enables proper state merging across nodes)
# ---------------------------------------------------------------------------


class GraphState(TypedDict, total=False):
    """TypedDict state used by LangGraph for automatic key-level merging.

    Each node returns a partial dict updating only the keys it modifies.
    LangGraph merges updates at the key level when using TypedDict.
    """

    # Input parameters
    video_length_minutes: int
    era_focus: Optional[str]
    geo_focus: Optional[str]
    topic_seed: Optional[str]
    tone: str
    sensitivity_level: str
    nonlinear_open: bool
    previous_format_tag: Optional[str]
    requested_format_tag: Optional[str]

    # Narrative lens / geo / mobility (optional expansions)
    narrative_lens: Optional[str | list[str]]
    lens_strength: float
    geo_scope: Optional[str]
    geo_anchor: Optional[str | list[str]]
    mobility_mode: Optional[str]

    # Derived parameters
    target_words: int
    min_words: int
    max_words: int
    rehook_interval: tuple[int, int]

    # Topic discovery & selection
    topic_candidates: list[TopicCandidate]
    chosen_topic: Optional[TopicCandidate]
    format_tag: str

    # Research
    research_corpus: list[dict[str, Any]]
    sources_log: list[SourceEntry]

    # Claims & cross-check
    claims: list[Claim]

    # Timeline & narrative
    timeline_beats: list[TimelineBeat]
    narrative_threads: list[NarrativeThread]

    # Emotional drivers
    emotional_drivers: list[EmotionalDriver]

    # Historiography
    consensus_vs_contested: list[dict[str, str]]

    # Script
    script_outline: list[ScriptSection]
    draft_script: str
    final_script: str

    # Quality
    qc_report: Optional[QCReport]
    emotional_intensity_score: float
    sensory_density_score: float
    validation_issues: list[str]

    # Internal tracking
    current_node: str
    errors: list[str]
    iteration_count: int
