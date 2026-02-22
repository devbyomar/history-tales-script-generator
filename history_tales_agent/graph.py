"""LangGraph workflow definition — the 16-node documentary generation pipeline."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from history_tales_agent.nodes.claims_extraction import claims_extraction_node
from history_tales_agent.nodes.cross_check import cross_check_node
from history_tales_agent.nodes.emotional_extraction import emotional_extraction_node
from history_tales_agent.nodes.emotional_intensity import emotional_intensity_node
from history_tales_agent.nodes.finalize import finalize_node
from history_tales_agent.nodes.format_rotation_guard import format_rotation_guard_node
from history_tales_agent.nodes.outline import outline_node
from history_tales_agent.nodes.quality_check import quality_check_node
from history_tales_agent.nodes.research_fetch import research_fetch_node
from history_tales_agent.nodes.retention_pass import retention_pass_node
from history_tales_agent.nodes.script_generation import script_generation_node
from history_tales_agent.nodes.sensory_density import sensory_density_node
from history_tales_agent.nodes.source_credibility import source_credibility_node
from history_tales_agent.nodes.timeline_builder import timeline_builder_node
from history_tales_agent.nodes.topic_discovery import topic_discovery_node
from history_tales_agent.nodes.topic_scoring import topic_scoring_node
from history_tales_agent.state import GraphState, QCReport
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


def build_graph() -> StateGraph:
    """Build and compile the 16-node LangGraph pipeline.

    Flow:
        TopicDiscovery → FormatRotationGuard → TopicScoring → ResearchFetch
        → SourceCredibility → ClaimsExtraction → CrossCheck → TimelineBuilder
        → EmotionalExtraction → Outline → ScriptGeneration → RetentionPass
        → EmotionalIntensity → SensoryDensity → QualityCheck
        ↳ (pass or max retries) → Finalize
        ↳ (fail + word count off) → ScriptGeneration (retry loop)
    """
    # Use TypedDict-based state for proper key-level merging across nodes
    workflow = StateGraph(GraphState)

    # --- Add all 16 nodes ---
    workflow.add_node("topic_discovery", topic_discovery_node)
    workflow.add_node("format_rotation_guard", format_rotation_guard_node)
    workflow.add_node("topic_scoring", topic_scoring_node)
    workflow.add_node("research_fetch", research_fetch_node)
    workflow.add_node("source_credibility", source_credibility_node)
    workflow.add_node("claims_extraction", claims_extraction_node)
    workflow.add_node("cross_check", cross_check_node)
    workflow.add_node("timeline_builder", timeline_builder_node)
    workflow.add_node("emotional_extraction", emotional_extraction_node)
    workflow.add_node("outline", outline_node)
    workflow.add_node("script_generation", script_generation_node)
    workflow.add_node("retention_pass", retention_pass_node)
    workflow.add_node("emotional_intensity", emotional_intensity_node)
    workflow.add_node("sensory_density", sensory_density_node)
    workflow.add_node("quality_check", quality_check_node)
    workflow.add_node("finalize", finalize_node)

    # --- Define edges ---
    workflow.set_entry_point("topic_discovery")

    workflow.add_edge("topic_discovery", "format_rotation_guard")
    workflow.add_edge("format_rotation_guard", "topic_scoring")
    workflow.add_edge("topic_scoring", "research_fetch")
    workflow.add_edge("research_fetch", "source_credibility")
    workflow.add_edge("source_credibility", "claims_extraction")
    workflow.add_edge("claims_extraction", "cross_check")
    workflow.add_edge("cross_check", "timeline_builder")
    workflow.add_edge("timeline_builder", "emotional_extraction")
    workflow.add_edge("emotional_extraction", "outline")
    workflow.add_edge("outline", "script_generation")
    workflow.add_edge("script_generation", "retention_pass")
    workflow.add_edge("retention_pass", "emotional_intensity")
    workflow.add_edge("emotional_intensity", "sensory_density")
    workflow.add_edge("sensory_density", "quality_check")

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
