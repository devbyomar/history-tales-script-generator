"""LangGraph workflow definition — the 15-node documentary generation pipeline.

Optimised from 18 nodes:
- FormatRotationGuard absorbed into TopicScoring
- SourceCredibility absorbed into ResearchFetch
- EmotionalIntensity + SensoryDensity merged into ScriptQualityScores
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from history_tales_agent.config import (
    ALL_FORMAT_TAGS,
    WORDS_PER_MINUTE,
    WORD_TOLERANCE,
)
from history_tales_agent.nodes.claims_extraction import claims_extraction_node
from history_tales_agent.nodes.cross_check import cross_check_node
from history_tales_agent.nodes.emotional_extraction import emotional_extraction_node
from history_tales_agent.nodes.fact_tighten import fact_tighten_node
from history_tales_agent.nodes.finalize import finalize_node
from history_tales_agent.nodes.hard_guardrails import hard_guardrails_node
from history_tales_agent.nodes.outline import outline_node
from history_tales_agent.nodes.quality_check import quality_check_node
from history_tales_agent.nodes.research_fetch import research_fetch_node
from history_tales_agent.nodes.retention_pass import retention_pass_node
from history_tales_agent.nodes.script_generation import script_generation_node
from history_tales_agent.nodes.script_quality_scores import script_quality_scores_node
from history_tales_agent.nodes.timeline_builder import timeline_builder_node
from history_tales_agent.nodes.topic_discovery import topic_discovery_node
from history_tales_agent.nodes.topic_scoring import topic_scoring_node
from history_tales_agent.state import GraphState, QCReport, TopicCandidate
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)

# Maximum QC → script_generation retry loops
MAX_QC_RETRIES = 2


def _qc_route(state: dict) -> str:
    """Decide whether to finalize or loop back for a rewrite.

    Routes back to script_generation when:
    - QC fails AND
    - We haven't exceeded MAX_QC_RETRIES iterations
    """
    qc: QCReport | None = state.get("qc_report")
    iteration = state.get("iteration_count", 0)

    if qc and not qc.overall_pass and iteration <= MAX_QC_RETRIES:
        logger.info(
            "qc_rewrite_loop",
            iteration=iteration,
            word_count=qc.word_count,
            target=qc.target_words,
            issues=len(qc.issues),
        )
        return "script_generation"

    return "finalize"


# ---------------------------------------------------------------------------
# Topic seed bypass — skips discovery + scoring when the user already
# knows what topic they want.
# ---------------------------------------------------------------------------

def topic_seed_bypass_node(state: dict[str, Any]) -> dict[str, Any]:
    """Create a TopicCandidate directly from topic_seed, skipping LLM discovery.

    Produces the same output keys as topic_scoring_node so downstream nodes
    (research_fetch, etc.) see no difference.
    """
    logger.info("node_start", node="TopicSeedBypass")

    topic_seed = state.get("topic_seed", "")
    video_length = state.get("video_length_minutes", 12)
    era_focus = state.get("era_focus") or ""
    geo_focus = state.get("geo_focus") or ""
    tone = state.get("tone", "cinematic-serious")
    requested_format = state.get("requested_format_tag")

    # Pick a format: honour requested_format, else default to Countdown
    format_tag = requested_format if requested_format else "Countdown"

    chosen = TopicCandidate(
        title=topic_seed,
        one_sentence_hook=topic_seed,
        era=era_focus,
        geo=geo_focus,
        core_pov="",
        timeline_window="",
        twist_points=["TBD", "TBD", "TBD"],  # min 3 required; research will fill real ones
        what_people_get_wrong="",
        format_tag=format_tag,
        likely_sources=[],
        score=100.0,  # user-selected — full confidence
    )

    target_words = video_length * WORDS_PER_MINUTE
    min_words = int(target_words * (1 - WORD_TOLERANCE))
    max_words = int(target_words * (1 + WORD_TOLERANCE))
    rehook_interval = (60, 90) if video_length <= 12 else (90, 120)

    logger.info(
        "topic_seed_bypass_complete",
        title=chosen.title,
        format=chosen.format_tag,
        target_words=target_words,
    )

    return {
        "chosen_topic": chosen,
        "format_tag": chosen.format_tag,
        "target_words": target_words,
        "min_words": min_words,
        "max_words": max_words,
        "rehook_interval": rehook_interval,
        "current_node": "TopicSeedBypass",
    }


def _entry_route(state: dict) -> str:
    """Route at entry: bypass discovery+scoring if skip_topic_exploration is True."""
    if state.get("skip_topic_exploration") and state.get("topic_seed"):
        return "topic_seed_bypass"
    return "topic_discovery"


def build_graph() -> StateGraph:
    """Build and compile the LangGraph pipeline.

    Flow (standard):
        TopicDiscovery → TopicScoring (incl. format rotation)
        → ResearchFetch → … → Finalize

    Flow (skip_topic_exploration=True):
        TopicSeedBypass → ResearchFetch → … → Finalize

    QC retry loop routes back to ScriptGeneration up to MAX_QC_RETRIES times.
    """
    workflow = StateGraph(GraphState)

    # --- Add nodes ---
    workflow.add_node("topic_discovery", topic_discovery_node)
    workflow.add_node("topic_scoring", topic_scoring_node)
    workflow.add_node("topic_seed_bypass", topic_seed_bypass_node)
    workflow.add_node("research_fetch", research_fetch_node)
    workflow.add_node("claims_extraction", claims_extraction_node)
    workflow.add_node("cross_check", cross_check_node)
    workflow.add_node("timeline_builder", timeline_builder_node)
    workflow.add_node("emotional_extraction", emotional_extraction_node)
    workflow.add_node("outline", outline_node)
    workflow.add_node("hard_guardrails", hard_guardrails_node)
    workflow.add_node("script_generation", script_generation_node)
    workflow.add_node("fact_tighten", fact_tighten_node)
    workflow.add_node("retention_pass", retention_pass_node)
    workflow.add_node("script_quality_scores", script_quality_scores_node)
    workflow.add_node("quality_check", quality_check_node)
    workflow.add_node("finalize", finalize_node)

    # --- Entry: conditional routing based on skip_topic_exploration ---
    workflow.set_conditional_entry_point(
        _entry_route,
        {
            "topic_discovery": "topic_discovery",
            "topic_seed_bypass": "topic_seed_bypass",
        },
    )

    # Standard discovery path
    workflow.add_edge("topic_discovery", "topic_scoring")
    workflow.add_edge("topic_scoring", "research_fetch")

    # Bypass path merges into the same downstream flow
    workflow.add_edge("topic_seed_bypass", "research_fetch")

    # Shared downstream edges
    workflow.add_edge("research_fetch", "claims_extraction")
    workflow.add_edge("claims_extraction", "cross_check")
    workflow.add_edge("cross_check", "timeline_builder")
    workflow.add_edge("timeline_builder", "emotional_extraction")
    workflow.add_edge("emotional_extraction", "outline")
    workflow.add_edge("outline", "hard_guardrails")
    workflow.add_edge("hard_guardrails", "script_generation")
    workflow.add_edge("script_generation", "fact_tighten")
    workflow.add_edge("fact_tighten", "retention_pass")
    workflow.add_edge("retention_pass", "script_quality_scores")
    workflow.add_edge("script_quality_scores", "quality_check")

    # Conditional: QC can loop back to script_generation or proceed to finalize
    workflow.add_conditional_edges(
        "quality_check",
        _qc_route,
        {
            "script_generation": "script_generation",
            "finalize": "finalize",
        },
    )

    workflow.add_edge("finalize", END)

    logger.info("graph_built", nodes=16)
    return workflow


def compile_graph():
    """Build and compile the graph, returning a runnable."""
    workflow = build_graph()
    return workflow.compile()
