"""Main entry point for the History Tales Script Generator agent.

Usage:
    python -m history_tales_agent.main --video-length 12 --era "World War II"
    python -m history_tales_agent.main --video-length 25 --topic-seed "D-Day" --tone urgent
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from history_tales_agent.config import (
    WORDS_PER_MINUTE,
    WORD_TOLERANCE,
    get_config,
)
from history_tales_agent.graph import compile_graph
from history_tales_agent.output.formatter import format_output
from history_tales_agent.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def run_agent(
    video_length_minutes: int,
    era_focus: Optional[str] = None,
    geo_focus: Optional[str] = None,
    topic_seed: Optional[str] = None,
    tone: str = "cinematic-serious",
    sensitivity_level: str = "general audiences",
    nonlinear_open: bool = True,
    previous_format_tag: Optional[str] = None,
    output_dir: str = "output",
) -> dict[str, Any]:
    """Run the full documentary script generation pipeline.

    Args:
        video_length_minutes: Target video duration in minutes.
        era_focus: Optional historical era constraint.
        geo_focus: Optional geographic focus.
        topic_seed: Optional starting topic idea.
        tone: Narrative tone preset.
        sensitivity_level: Content sensitivity level.
        nonlinear_open: Whether to use nonlinear opening.
        previous_format_tag: Previous format for rotation enforcement.
        output_dir: Directory for output files.

    Returns:
        Dict containing all pipeline state including final_script, qc_report, etc.
    """
    # Validate config
    config = get_config()
    setup_logging(config.log_level)

    logger.info(
        "agent_start",
        video_length=video_length_minutes,
        era=era_focus,
        geo=geo_focus,
        topic_seed=topic_seed,
        tone=tone,
    )

    # Compute word targets
    target_words = video_length_minutes * WORDS_PER_MINUTE
    min_words = int(target_words * (1 - WORD_TOLERANCE))
    max_words = int(target_words * (1 + WORD_TOLERANCE))

    # Determine re-hook interval
    if video_length_minutes <= 12:
        rehook_interval = (60, 90)
    else:
        rehook_interval = (90, 120)

    # Build initial state
    initial_state = {
        "video_length_minutes": video_length_minutes,
        "era_focus": era_focus,
        "geo_focus": geo_focus,
        "topic_seed": topic_seed,
        "tone": tone,
        "sensitivity_level": sensitivity_level,
        "nonlinear_open": nonlinear_open,
        "previous_format_tag": previous_format_tag,
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

    # Compile and run the graph
    app = compile_graph()

    logger.info("pipeline_starting", target_words=target_words)

    final_state = app.invoke(initial_state)

    # Write output files
    output_path = format_output(final_state, output_dir)
    logger.info("output_written", path=str(output_path))

    return final_state


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="History Tales Script Generator — AI-powered documentary scriptwriting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m history_tales_agent.main --video-length 12 --era "World War II"
  python -m history_tales_agent.main --video-length 25 --topic-seed "D-Day" --tone urgent
  python -m history_tales_agent.main --video-length 10 --geo "Pacific Theater" --tone fast-paced
        """,
    )

    parser.add_argument(
        "--video-length",
        type=int,
        required=True,
        help="Target video length in minutes",
    )
    parser.add_argument(
        "--era",
        type=str,
        default=None,
        help="Historical era focus (e.g., 'World War II', 'Cold War')",
    )
    parser.add_argument(
        "--geo",
        type=str,
        default=None,
        help="Geographic focus (e.g., 'Western Europe', 'Pacific Theater')",
    )
    parser.add_argument(
        "--topic-seed",
        type=str,
        default=None,
        help="Starting topic idea to bias discovery",
    )
    parser.add_argument(
        "--tone",
        type=str,
        default="cinematic-serious",
        choices=[
            "cinematic-serious",
            "investigative",
            "fast-paced",
            "somber",
            "restrained",
            "urgent",
            "claustrophobic",
            "reflective",
        ],
        help="Narrative tone (default: cinematic-serious)",
    )
    parser.add_argument(
        "--sensitivity",
        type=str,
        default="general audiences",
        choices=["general audiences", "teen", "mature"],
        help="Content sensitivity level",
    )
    parser.add_argument(
        "--linear-open",
        action="store_true",
        help="Use linear (chronological) opening instead of nonlinear",
    )
    parser.add_argument(
        "--previous-format",
        type=str,
        default=None,
        choices=["Countdown", "One Room", "Two Truths", "Chain Reaction", "Impossible Choice", "Hunt"],
        help="Previous episode format tag for rotation enforcement",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Output directory (default: output/)",
    )

    args = parser.parse_args()

    try:
        result = run_agent(
            video_length_minutes=args.video_length,
            era_focus=args.era,
            geo_focus=args.geo,
            topic_seed=args.topic_seed,
            tone=args.tone,
            sensitivity_level=args.sensitivity,
            nonlinear_open=not args.linear_open,
            previous_format_tag=args.previous_format,
            output_dir=args.output_dir,
        )

        # Print summary
        chosen = result.get("chosen_topic")
        qc = result.get("qc_report")
        script = result.get("final_script", "")

        print("\n" + "=" * 70)
        print("✅ DOCUMENTARY SCRIPT GENERATED")
        print("=" * 70)
        if chosen:
            print(f"📌 Title: {chosen.title}")
            print(f"🎬 Format: {chosen.format_tag}")
            print(f"🎯 Score: {chosen.score:.1f}/100")
        print(f"📝 Words: {len(script.split())}")
        print(f"⏱  Target: {result.get('target_words')} words ({args.video_length} min)")
        print(f"🎭 Emotional Intensity: {result.get('emotional_intensity_score', 0):.1f}/100")
        print(f"👁  Sensory Density: {result.get('sensory_density_score', 0):.1f}/100")
        print(f"📚 Sources: {len(result.get('sources_log', []))}")
        print(f"📋 Claims: {len(result.get('claims', []))}")
        if qc:
            print(f"✅ QC: {'PASS' if qc.overall_pass else 'FAIL'}")
            if qc.issues:
                for issue in qc.issues[:5]:
                    print(f"   ⚠️  {issue}")
        print(f"\n📁 Output: {args.output_dir}/")
        print("=" * 70)

    except KeyboardInterrupt:
        print("\n⏹  Cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        logger.exception("agent_failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
