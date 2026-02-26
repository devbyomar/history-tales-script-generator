"""Pipeline runner — executes the LangGraph pipeline with SSE progress events.

Wraps the existing `run_agent()` function and intercepts node transitions
to emit real-time progress updates via the RunStore.
"""

from __future__ import annotations

import asyncio
import threading
import traceback
from datetime import datetime
from typing import Any

from api.schemas import NodeProgress
from api.store import run_store


class _PipelineCancelled(Exception):
    """Raised when a pipeline run is cancelled by the user."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"Run {run_id} cancelled by user")

# Pipeline node order (matches graph.py edge definitions)
PIPELINE_NODES = [
    "topic_discovery",
    "format_rotation_guard",
    "topic_scoring",
    "research_fetch",
    "source_credibility",
    "claims_extraction",
    "cross_check",
    "timeline_builder",
    "emotional_extraction",
    "outline",
    "hard_guardrails",
    "script_generation",
    "fact_tighten",
    "retention_pass",
    "emotional_intensity",
    "sensory_density",
    "quality_check",
    "finalize",
]

NODE_LABELS = {
    "topic_discovery": "Discovering Topics",
    "format_rotation_guard": "Checking Format Rotation",
    "topic_scoring": "Scoring Topics",
    "research_fetch": "Fetching Research",
    "source_credibility": "Evaluating Source Credibility",
    "claims_extraction": "Extracting Claims",
    "cross_check": "Cross-Checking Facts",
    "timeline_builder": "Building Timeline",
    "emotional_extraction": "Extracting Emotional Drivers",
    "outline": "Creating Script Outline",
    "hard_guardrails": "Enforcing Hard Guardrails",
    "script_generation": "Writing Script",
    "fact_tighten": "Fact-Checking & Trace Tags",
    "retention_pass": "Applying Retention Hooks",
    "emotional_intensity": "Scoring Emotional Intensity",
    "sensory_density": "Checking Sensory Density",
    "quality_check": "Running Quality Check",
    "finalize": "Finalizing Output",
}


async def run_pipeline(run_id: str, params: dict[str, Any]) -> None:
    """Execute the pipeline in a background thread with progress events.

    Uses LangGraph's stream() to intercept node completions and publish
    SSE events. Falls back to invoke() if streaming isn't available.
    """
    from history_tales_agent.config import WORDS_PER_MINUTE, WORD_TOLERANCE, get_config
    from history_tales_agent.graph import compile_graph
    from history_tales_agent.utils.logging import setup_logging

    try:
        config = get_config()
        setup_logging(config.log_level)

        # Compute word targets
        video_length = params["video_length_minutes"]
        target_words = video_length * WORDS_PER_MINUTE
        min_words = int(target_words * (1 - WORD_TOLERANCE))
        max_words = int(target_words * (1 + WORD_TOLERANCE))

        # Determine re-hook interval
        rehook_interval = (60, 90) if video_length <= 12 else (90, 120)

        # Build initial state
        initial_state = {
            "video_length_minutes": video_length,
            "era_focus": params.get("era_focus"),
            "geo_focus": params.get("geo_focus"),
            "topic_seed": params.get("topic_seed"),
            "tone": params.get("tone", "cinematic-serious"),
            "sensitivity_level": params.get("sensitivity_level", "general audiences"),
            "nonlinear_open": params.get("nonlinear_open", True),
            "previous_format_tag": params.get("previous_format_tag"),
            "requested_format_tag": params.get("requested_format_tag"),
            "narrative_lens": params.get("narrative_lens"),
            "lens_strength": max(0.0, min(1.0, params.get("lens_strength", 0.6))),
            "geo_scope": params.get("geo_scope"),
            "geo_anchor": params.get("geo_anchor"),
            "mobility_mode": params.get("mobility_mode"),
            "target_words": target_words,
            "min_words": min_words,
            "max_words": max_words,
            "rehook_interval": rehook_interval,
            "topic_candidates": [],
            "chosen_topic": None,
            "research_corpus": [],
            "sources_log": [],
            "claims": [],
            "timeline_beats": [],
            "narrative_threads": [],
            "emotional_drivers": [],
            "consensus_vs_contested": [],
            "script_outline": [],
            "draft_script": "",
            "final_script": "",
            "qc_report": None,
            "format_tag": "",
            "emotional_intensity_score": 0.0,
            "sensory_density_score": 0.0,
            "validation_issues": [],
            "current_node": "",
            "errors": [],
            "iteration_count": 0,
        }

        app = compile_graph()

        # Stream node-by-node for real-time progress
        completed_nodes: set[str] = set()
        final_state: dict[str, Any] = {}

        # Capture the running event loop BEFORE entering the thread
        loop = asyncio.get_running_loop()

        # Threading event for cross-thread cancellation signalling
        cancel_event = threading.Event()
        run_store.set_cancel_event(run_id, cancel_event)

        # Run the pipeline with streaming in a thread to avoid blocking the event loop
        def _run_sync():
            nonlocal final_state
            last_state = {}
            for event in app.stream(initial_state, stream_mode="updates"):
                # ---- Cancellation check (between every node) ----
                if cancel_event.is_set():
                    return  # Exit silently — coroutine handles cleanup

                for node_name, node_output in event.items():
                    last_state.update(node_output)
                    completed_nodes.add(node_name)

                    # Check again after processing each node output
                    if cancel_event.is_set():
                        return  # Exit silently

                    # Publish progress event
                    node_index = (
                        PIPELINE_NODES.index(node_name) + 1
                        if node_name in PIPELINE_NODES
                        else len(completed_nodes)
                    )

                    # Extract interesting data for the frontend
                    extra_data = _extract_node_data(node_name, node_output)

                    progress = NodeProgress(
                        run_id=run_id,
                        node=node_name,
                        status="completed",
                        node_index=node_index,
                        message=NODE_LABELS.get(node_name, node_name),
                        data=extra_data,
                    )
                    # Schedule coroutine from sync context using the captured loop
                    loop.call_soon_threadsafe(
                        lambda p=progress: asyncio.ensure_future(
                            run_store.publish_event(p)
                        )
                    )

            # Only set final_state if we weren't cancelled
            if not cancel_event.is_set():
                final_state = {**initial_state, **last_state}

        # Run in thread pool, but race against a cancellation watcher
        # so the coroutine exits immediately on cancel even if the thread
        # is blocked inside an LLM call.
        thread_future = loop.run_in_executor(None, _run_sync)
        _cancelled = False

        async def _cancel_watcher():
            """Poll the cancel event from the async side."""
            while not cancel_event.is_set():
                await asyncio.sleep(0.5)
            # Signal detected — don't raise, just return so we handle it below
            return "cancelled"

        watcher_task = asyncio.create_task(_cancel_watcher())

        try:
            # Wait for whichever finishes first: pipeline or cancellation
            done, pending = await asyncio.wait(
                [thread_future, watcher_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            # Cancel the pending tasks (cleanup)
            for t in pending:
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, _PipelineCancelled):
                    pass

            # Check if cancellation won the race
            for t in done:
                if t is watcher_task:
                    _cancelled = True
                elif t.exception() is not None:
                    raise t.exception()

        except asyncio.CancelledError:
            cancel_event.set()
            _cancelled = True

        if _cancelled:
            raise _PipelineCancelled(run_id)

        # Update the run store with results
        chosen = final_state.get("chosen_topic")
        qc = final_state.get("qc_report")
        script = final_state.get("final_script", "")

        # Generate ElevenLabs TTS variants (pure text transforms — no LLM calls)
        from history_tales_agent.output.elevenlabs_formatter import (
            format_elevenlabs_v3,
            format_elevenlabs_flash,
        )
        script_el_v3 = format_elevenlabs_v3(script) if script else ""
        script_el_flash = format_elevenlabs_flash(script) if script else ""

        update_data: dict[str, Any] = {
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "final_script": script,
            "script_elevenlabs_v3": script_el_v3,
            "script_elevenlabs_flash": script_el_flash,
            "word_count": len(script.split()) if script else 0,
            "target_words": target_words,
            "emotional_intensity": final_state.get("emotional_intensity_score", 0),
            "sensory_density": final_state.get("sensory_density_score", 0),
            "source_count": len(final_state.get("sources_log", [])),
            "claim_count": len(final_state.get("claims", [])),
            "errors": final_state.get("errors", []),
        }

        if chosen:
            update_data["title"] = chosen.title if hasattr(chosen, "title") else str(chosen.get("title", ""))
            update_data["format_tag"] = chosen.format_tag if hasattr(chosen, "format_tag") else str(chosen.get("format_tag", ""))
            update_data["topic_score"] = chosen.score if hasattr(chosen, "score") else float(chosen.get("score", 0))

        if qc:
            update_data["qc_pass"] = qc.overall_pass if hasattr(qc, "overall_pass") else qc.get("overall_pass", False)
            update_data["qc_issues"] = (qc.issues if hasattr(qc, "issues") else qc.get("issues", []))[:10]
            update_data["qc_report"] = qc.model_dump() if hasattr(qc, "model_dump") else dict(qc)

        # Serialize sources & claims for storage
        sources = final_state.get("sources_log", [])
        if sources and hasattr(sources[0], "model_dump"):
            update_data["sources_log"] = [s.model_dump() for s in sources]
        else:
            update_data["sources_log"] = sources

        claims = final_state.get("claims", [])
        if claims and hasattr(claims[0], "model_dump"):
            update_data["claims"] = [c.model_dump() for c in claims]
        else:
            update_data["claims"] = claims

        run_store.update_run(run_id, **update_data)

        # Publish final completion event
        await run_store.publish_event(
            NodeProgress(
                run_id=run_id,
                node="__complete__",
                status="completed",
                node_index=18,
                total_nodes=18,
                message="Pipeline complete!",
            )
        )

    except _PipelineCancelled:
        # User-initiated cancellation — mark run cleanly
        run_store.update_run(
            run_id,
            status="cancelled",
            completed_at=datetime.utcnow().isoformat(),
            errors=["Cancelled by user"],
        )
        await run_store.publish_event(
            NodeProgress(
                run_id=run_id,
                node="__cancelled__",
                status="failed",
                node_index=0,
                message="Pipeline cancelled by user",
            )
        )

    except asyncio.CancelledError:
        # asyncio task cancellation (from task.cancel())
        run_store.update_run(
            run_id,
            status="cancelled",
            completed_at=datetime.utcnow().isoformat(),
            errors=["Cancelled by user"],
        )
        await run_store.publish_event(
            NodeProgress(
                run_id=run_id,
                node="__cancelled__",
                status="failed",
                node_index=0,
                message="Pipeline cancelled by user",
            )
        )

    except Exception as e:
        # Mark run as failed
        run_store.update_run(
            run_id,
            status="failed",
            completed_at=datetime.utcnow().isoformat(),
            errors=[str(e), traceback.format_exc()],
        )
        await run_store.publish_event(
            NodeProgress(
                run_id=run_id,
                node="__error__",
                status="failed",
                node_index=0,
                message=f"Pipeline failed: {str(e)[:200]}",
            )
        )


def _extract_node_data(node_name: str, output: dict) -> dict[str, Any] | None:
    """Extract interesting data from a node's output for the frontend."""
    data: dict[str, Any] = {}

    if node_name == "topic_discovery":
        candidates = output.get("topic_candidates", [])
        if candidates:
            data["candidate_count"] = len(candidates)
            data["candidates"] = [
                {
                    "title": (c.title if hasattr(c, "title") else c.get("title", "")),
                    "hook": (c.one_sentence_hook if hasattr(c, "one_sentence_hook") else c.get("one_sentence_hook", "")),
                }
                for c in candidates[:5]
            ]

    elif node_name == "topic_scoring":
        chosen = output.get("chosen_topic")
        if chosen:
            data["chosen_title"] = chosen.title if hasattr(chosen, "title") else chosen.get("title", "")
            data["score"] = chosen.score if hasattr(chosen, "score") else chosen.get("score", 0)

    elif node_name == "research_fetch":
        corpus = output.get("research_corpus", [])
        sources = output.get("sources_log", [])
        data["sources_found"] = len(sources)
        data["corpus_size"] = len(corpus)

    elif node_name == "claims_extraction":
        claims = output.get("claims", [])
        data["claims_extracted"] = len(claims)

    elif node_name == "script_generation":
        script = output.get("final_script", "")
        data["word_count"] = len(script.split()) if script else 0

    elif node_name == "quality_check":
        qc = output.get("qc_report")
        if qc:
            data["qc_pass"] = qc.overall_pass if hasattr(qc, "overall_pass") else qc.get("overall_pass", False)
            data["word_count"] = qc.word_count if hasattr(qc, "word_count") else qc.get("word_count", 0)

    return data if data else None
