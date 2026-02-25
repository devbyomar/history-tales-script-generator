"""Geographic Engine — spatial storytelling controls.

Provides geo_scope, geo_anchor, and mobility_mode prompt injection.
When none of these parameters are set, helpers return empty strings →
zero impact on existing behaviour.
"""

from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Valid values (used for validation + CLI choices)
# ---------------------------------------------------------------------------

GEO_SCOPE_VALUES = [
    "single_city",
    "region",
    "country",
    "theater",
    "global",
]

MOBILITY_MODE_VALUES = [
    "fixed_site",
    "route_based",
    "multi_site",
    "theater_wide",
]


# ---------------------------------------------------------------------------
# Prompt-building helpers
# ---------------------------------------------------------------------------

def build_geo_prompt_block(
    geo_scope: Optional[str] = None,
    geo_anchor: Optional[str | list[str]] = None,
    mobility_mode: Optional[str] = None,
) -> str:
    """Build a prompt block that tells the LLM how to apply geographic/spatial controls.

    Returns empty string when all inputs are None → backward-compatible.
    """
    if not geo_scope and not geo_anchor and not mobility_mode:
        return ""

    parts = ["\n\n--- GEOGRAPHIC & SPATIAL INSTRUCTIONS ---"]

    # ── geo_scope ──
    if geo_scope:
        scope_guidance = {
            "single_city": (
                "The story is confined to a SINGLE CITY. All acts must take place "
                "within this city's boundaries. Emphasise neighbourhood-level geography: "
                "streets, buildings, bridges, squares. The audience should feel the city's "
                "layout as part of the tension."
            ),
            "region": (
                "The story spans a REGION (e.g. a province, a valley, a coastline). "
                "Acts may move between locations within the region. Distances and travel "
                "times matter — make them tangible."
            ),
            "country": (
                "The story spans a COUNTRY. Cross-cut between capital/centre and periphery. "
                "Show how the same event looks different from different parts of the country."
            ),
            "theater": (
                "The story spans a THEATER OF OPERATIONS (e.g. Western Front, Pacific Theater). "
                "Use map-scale thinking: fronts, supply lines, strategic positions. "
                "Cross-cut between command and field level."
            ),
            "global": (
                "The story spans MULTIPLE CONTINENTS or the global stage. "
                "Cross-cut between distant locations. Emphasise communication delays, "
                "time zones, and how distance distorts information."
            ),
        }
        parts.append(f"Geographic scope: {geo_scope}")
        parts.append(scope_guidance.get(geo_scope, f"Scope: {geo_scope}"))
        parts.append("")

    # ── geo_anchor ──
    if geo_anchor:
        if isinstance(geo_anchor, list):
            anchor_str = ", ".join(geo_anchor)
        else:
            anchor_str = geo_anchor
        parts.append(f"Geographic anchor(s): {anchor_str}")
        parts.append(
            "ANCHOR RULES:\n"
            "- The anchor is a REAL physical location that serves as the story's spatial gravity centre.\n"
            "- The outline must RETURN to the anchor at least once per act for structural cohesion.\n"
            "- The anchor should be described with at least one specific sensory/physical detail on first appearance.\n"
            "- Use the anchor to ground time jumps and cross-cuts — 'Back at [anchor]…'\n"
            "- The anchor is a VISUAL and NARRATIVE recurring element, not just a name."
        )
        parts.append("")

    # ── mobility_mode ──
    if mobility_mode:
        mode_guidance = {
            "fixed_site": (
                "FIXED-SITE MODE: The story is anchored in ONE structure or location "
                "(a bunker, a building, a ship, a control room).\n"
                "- Emphasise claustrophobia, system pressure, and what happens INSIDE.\n"
                "- Act transitions should mark changes in what the people inside KNOW, "
                "not where they ARE.\n"
                "- Cross-cuts to the outside world should create tension by showing what "
                "the people inside cannot see.\n"
                "- Pacing: slower, pressure-building. Time moves differently when you can't leave."
            ),
            "route_based": (
                "ROUTE-BASED MODE: The story follows MOVEMENT — a convoy, a march, "
                "a migration, an escape, a flight path.\n"
                "- Emphasise timing, distance, exposure, and sequence.\n"
                "- Act transitions should mark DISTANCE COVERED or OBSTACLES ENCOUNTERED.\n"
                "- Cross-cuts should show what's ahead on the route (unknown to the travellers) "
                "or what's behind them (pursuit, consequence).\n"
                "- Pacing: forward-driven. The audience should feel the route narrowing or opening."
            ),
            "multi_site": (
                "MULTI-SITE MODE: The story cross-cuts between 2–4 KEY LOCATIONS.\n"
                "- Limit to at most 4 recurring locations — more than that disorients the listener.\n"
                "- Each location should have a distinct sensory identity on first appearance.\n"
                "- Cross-cuts must be MOTIVATED — cut between sites when a decision at one "
                "affects the situation at another.\n"
                "- Pacing: rhythmic alternation. Build parallel tension across sites."
            ),
            "theater_wide": (
                "THEATER-WIDE MODE: Broad operational movement across a large area.\n"
                "- Use map-level orientation: compass directions, distances, front lines.\n"
                "- Act transitions should mark operational phases or strategic shifts.\n"
                "- Cross-cut between strategic (headquarters, planning) and tactical (field, ground).\n"
                "- Pacing: panoramic with zoom-ins. Wide shot → close-up → wide shot."
            ),
        }
        parts.append(f"Mobility mode: {mobility_mode}")
        parts.append(mode_guidance.get(mobility_mode, f"Mode: {mobility_mode}"))
        parts.append("")

    parts.append(
        "GEOGRAPHIC CONSTRAINTS (mandatory):\n"
        "- Geographic/spatial controls must NOT alter historical accuracy.\n"
        "- Geographic/spatial controls must NOT override active lens constraints.\n"
        "- Acts must demonstrate spatial awareness — the audience should always know WHERE they are.\n"
        "- Movement must be traceable — if a character moves, show or imply the distance and time."
    )
    parts.append("--- END GEOGRAPHIC INSTRUCTIONS ---\n")
    return "\n".join(parts)


def build_planning_metadata(
    lenses: list | None = None,
    geo_scope: str | None = None,
    geo_anchor: str | list[str] | None = None,
    mobility_mode: str | None = None,
) -> str:
    """Build a metadata block for the planning/outline node output.

    Used so that downstream nodes can see what narrative controls are active.
    Returns empty string when nothing is active.
    """
    if not any([lenses, geo_scope, geo_anchor, mobility_mode]):
        return ""

    parts = ["[NARRATIVE CONTROLS METADATA]"]
    if lenses:
        lens_ids = [l.lens_id if hasattr(l, "lens_id") else str(l) for l in lenses]
        parts.append(f"  Active lenses: {', '.join(lens_ids)}")
    if geo_scope:
        parts.append(f"  Geo scope: {geo_scope}")
    if geo_anchor:
        anchor = ", ".join(geo_anchor) if isinstance(geo_anchor, list) else geo_anchor
        parts.append(f"  Geo anchor: {anchor}")
    if mobility_mode:
        parts.append(f"  Mobility mode: {mobility_mode}")
    parts.append("")
    return "\n".join(parts)
