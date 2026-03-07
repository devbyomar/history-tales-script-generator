"""LangGraph workflow definition — the 15-node documentary generation pipeline.

Optimised from 18 nodes:
- FormatRotationGuard absorbed into TopicScoring
- SourceCredibility absorbed into ResearchFetch
- EmotionalIntensity + SensoryDensity merged into ScriptQualityScores
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

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
    """Build and compile the 15-node LangGraph pipeline.

    Flow:
        TopicDiscovery → TopicScoring (incl. format rotation)
        → ResearchFetch (incl. source credibility) → ClaimsExtraction
        → CrossCheck → TimelineBuilder → EmotionalExtraction → Outline
        → HardGuardrails → ScriptGeneration → FactTighten → RetentionPass
        → ScriptQualityScores → QualityCheck
        ↳ (pass or max retries) → Finalize
        ↳ (fail + word count off) → ScriptGeneration (retry loop)
    """
    workflow = StateGraph(GraphState)

    # --- Add all 15 nodes ---
    workflow.add_node("topic_discovery", topic_discovery_node)
    workflow.add_node("topic_scoring", topic_scoring_node)
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

    # --- Define edges ---
    workflow.set_entry_point("topic_discovery")

    workflow.add_edge("topic_discovery", "topic_scoring")
    workflow.add_edge("topic_scoring", "research_fetch")
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

    logger.info("graph_built", nodes=15)
    return workflow


def compile_graph():
    """Build and compile the graph, returning a runnable."""
    workflow = build_graph()
    return workflow.compile()
