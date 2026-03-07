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
    SPEECHIFY_WORDS_PER_MINUTE,
    SPEECHIFY_WORD_TOLERANCE,
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
    requested_format_tag: Optional[str] = None,
    narrative_lens: Optional[str] = None,
    lens_strength: float = 0.6,
    geo_scope: Optional[str] = None,
    geo_anchor: Optional[str] = None,
    mobility_mode: Optional[str] = None,
    output_dir: str = "output",
    output_mode: str = "standard",
    skip_topic_exploration: bool = False,
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
        requested_format_tag: Force a specific format tag.
        narrative_lens: Optional narrative lens(es) — comma-separated or single.
        lens_strength: How strongly the lens biases storytelling (0.0–1.0).
        geo_scope: Optional geographic scope constraint.
        geo_anchor: Optional physical focal point for spatial cohesion.
        mobility_mode: Optional spatial narrative mode.
        output_dir: Directory for output files.
        output_mode: Output mode — "standard" or "speechify_export".
        skip_topic_exploration: If True, skip discovery & scoring; use topic_seed directly.

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
        narrative_lens=narrative_lens,
        lens_strength=lens_strength,
        geo_scope=geo_scope,
        geo_anchor=geo_anchor,
        mobility_mode=mobility_mode,
    )

    # Compute word targets — Speechify reads at 115 WPM vs 155 WPM standard
    if output_mode == "speechify_export":
        wpm = SPEECHIFY_WORDS_PER_MINUTE
        tolerance = SPEECHIFY_WORD_TOLERANCE
    else:
        wpm = WORDS_PER_MINUTE
        tolerance = WORD_TOLERANCE

    target_words = video_length_minutes * wpm
    min_words = int(target_words * (1 - tolerance))
    max_words = int(target_words * (1 + tolerance))

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
        "requested_format_tag": requested_format_tag,
        "narrative_lens": narrative_lens,
        "lens_strength": max(0.0, min(1.0, lens_strength)),
        "geo_scope": geo_scope,
        "geo_anchor": geo_anchor,
        "mobility_mode": mobility_mode,
        "output_mode": output_mode,
        "skip_topic_exploration": skip_topic_exploration,
        "target_words": target_words,
        "min_words": min_words,
        "max_words": max_words,
        "rehook_interval": rehook_interval,
        "words_per_minute": wpm,
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
        "narratability_score": 0.0,
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
        "--format",
        type=str,
        default=None,
        choices=["Countdown", "One Room", "Two Truths", "Chain Reaction", "Impossible Choice", "Hunt"],
        help="Force a specific episode format",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Output directory (default: output/)",
    )
    parser.add_argument(
        "--output-mode",
        type=str,
        default="standard",
        choices=["standard", "speechify_export"],
        help="Output mode — 'standard' (155 WPM) or 'speechify_export' (115 WPM, plain narration)",
    )
    parser.add_argument(
        "--skip-topic-exploration",
        action="store_true",
        help="Skip topic discovery & scoring — use --topic-seed directly as the chosen topic",
    )

    # ── Narrative lens / geo / mobility (optional expansions) ──
    parser.add_argument(
        "--lens",
        type=str,
        default=None,
        help=(
            "Narrative lens(es) — comma-separated. "
            "E.g. 'civilians', 'medics,logistics', 'spies'. "
            "See docs for full list."
        ),
    )
    parser.add_argument(
        "--lens-strength",
        type=float,
        default=0.6,
        help="How strongly the lens biases storytelling (0.0–1.0, default 0.6)",
    )
    parser.add_argument(
        "--geo-scope",
        type=str,
        default=None,
        choices=["single_city", "region", "country", "theater", "global"],
        help="Geographic scope of the story",
    )
    parser.add_argument(
        "--geo-anchor",
        type=str,
        default=None,
        help=(
            "Physical focal point for spatial cohesion. "
            "E.g. 'Tempelhof Airport', 'Ludendorff Bridge'"
        ),
    )
    parser.add_argument(
        "--mobility",
        type=str,
        default=None,
        choices=["fixed_site", "route_based", "multi_site", "theater_wide"],
        help="Spatial narrative mode",
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
            requested_format_tag=args.format,
            narrative_lens=args.lens,
            lens_strength=args.lens_strength,
            geo_scope=args.geo_scope,
            geo_anchor=args.geo_anchor,
            mobility_mode=args.mobility,
            output_dir=args.output_dir,
            output_mode=args.output_mode,
            skip_topic_exploration=args.skip_topic_exploration,
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
        # Show narrative controls if active
        if args.lens:
            print(f"🔍 Lens: {args.lens} (strength {args.lens_strength:.1f})")
        if args.geo_scope:
            print(f"🌍 Geo scope: {args.geo_scope}")
        if args.geo_anchor:
            print(f"📍 Geo anchor: {args.geo_anchor}")
        if args.mobility:
            print(f"🚗 Mobility: {args.mobility}")
        if args.output_mode != "standard":
            print(f"🔊 Output mode: {args.output_mode}")
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
