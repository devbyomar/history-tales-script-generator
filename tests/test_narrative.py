"""Tests for the narrative lens, geographic engine, and mobility mode subsystem."""

from __future__ import annotations

import pytest

from history_tales_agent.narrative.lenses import (
    ALL_LENS_IDS,
    LENS_REGISTRY,
    LensContract,
    build_lens_prompt_block,
    get_lens,
    resolve_lenses,
)
from history_tales_agent.narrative.geo import (
    GEO_SCOPE_VALUES,
    MOBILITY_MODE_VALUES,
    build_geo_prompt_block,
    build_planning_metadata,
)


# ═══════════════════════════════════════════════════════════════
# Lens Registry
# ═══════════════════════════════════════════════════════════════


class TestLensRegistry:
    """Verify the lens registry is well-formed."""

    def test_all_lenses_have_required_fields(self):
        for lid, contract in LENS_REGISTRY.items():
            assert contract.lens_id == lid
            assert contract.short_description
            assert len(contract.scene_priorities) >= 2
            assert len(contract.tension_patterns) >= 2
            assert len(contract.preferred_artifacts) >= 2
            assert len(contract.forbidden_moves) >= 1
            assert len(contract.hook_templates) >= 1

    def test_minimum_lens_count(self):
        # At least 20 lenses should exist
        assert len(LENS_REGISTRY) >= 20

    def test_all_lens_ids_sorted(self):
        assert ALL_LENS_IDS == sorted(ALL_LENS_IDS)


# ═══════════════════════════════════════════════════════════════
# Lens Lookup
# ═══════════════════════════════════════════════════════════════


class TestGetLens:
    def test_exact_id(self):
        assert get_lens("civilians") is not None
        assert get_lens("civilians").lens_id == "civilians"

    def test_case_insensitive(self):
        assert get_lens("CIVILIANS") is not None
        assert get_lens("Medics") is not None

    def test_hyphen_to_underscore(self):
        assert get_lens("tank-crews") is not None

    def test_space_to_underscore(self):
        assert get_lens("tank crews") is not None

    def test_unknown_returns_none(self):
        assert get_lens("nonexistent_lens_xyz") is None


# ═══════════════════════════════════════════════════════════════
# Lens Resolution
# ═══════════════════════════════════════════════════════════════


class TestResolveLenses:
    def test_none_returns_empty(self):
        assert resolve_lenses(None) == []

    def test_single_string(self):
        result = resolve_lenses("civilians")
        assert len(result) == 1
        assert result[0].lens_id == "civilians"

    def test_comma_separated(self):
        result = resolve_lenses("civilians,medics,spies")
        assert len(result) == 3
        assert [l.lens_id for l in result] == ["civilians", "medics", "spies"]

    def test_list_input(self):
        result = resolve_lenses(["logistics", "engineers"])
        assert len(result) == 2

    def test_unknown_ids_skipped(self):
        result = resolve_lenses("civilians,unknown_xyz,medics")
        assert len(result) == 2
        assert [l.lens_id for l in result] == ["civilians", "medics"]

    def test_empty_string_returns_empty(self):
        assert resolve_lenses("") == []

    def test_empty_list_returns_empty(self):
        assert resolve_lenses([]) == []


# ═══════════════════════════════════════════════════════════════
# Lens Prompt Block
# ═══════════════════════════════════════════════════════════════


class TestBuildLensPromptBlock:
    def test_empty_lenses_returns_empty(self):
        assert build_lens_prompt_block([]) == ""

    def test_single_lens_block(self):
        lenses = resolve_lenses("medics")
        block = build_lens_prompt_block(lenses, strength=0.7)
        assert "NARRATIVE LENS INSTRUCTIONS" in block
        assert "medics" in block
        assert "0.7" in block
        assert "strongly" in block

    def test_multiple_lens_block(self):
        lenses = resolve_lenses("civilians,logistics")
        block = build_lens_prompt_block(lenses, strength=0.5)
        assert "civilians" in block
        assert "logistics" in block
        assert "moderately" in block

    def test_low_strength(self):
        lenses = resolve_lenses("spies")
        block = build_lens_prompt_block(lenses, strength=0.1)
        assert "lightly" in block

    def test_strength_clamped(self):
        lenses = resolve_lenses("medics")
        block_high = build_lens_prompt_block(lenses, strength=5.0)
        assert "1.0" in block_high
        block_low = build_lens_prompt_block(lenses, strength=-1.0)
        assert "0.0" in block_low

    def test_contains_forbidden_moves(self):
        lenses = resolve_lenses("medics")
        block = build_lens_prompt_block(lenses)
        assert "Forbidden moves" in block

    def test_contains_scene_priorities(self):
        lenses = resolve_lenses("spies")
        block = build_lens_prompt_block(lenses)
        assert "Scene priorities" in block

    def test_contains_safety_rules(self):
        lenses = resolve_lenses("civilians")
        block = build_lens_prompt_block(lenses)
        assert "NEVER override facts" in block
        assert "NEVER invent fictional internal thoughts" in block
        assert "NEVER suppress uncertainty" in block


# ═══════════════════════════════════════════════════════════════
# Geographic Engine
# ═══════════════════════════════════════════════════════════════


class TestBuildGeoPromptBlock:
    def test_all_none_returns_empty(self):
        assert build_geo_prompt_block() == ""

    def test_geo_scope_only(self):
        block = build_geo_prompt_block(geo_scope="single_city")
        assert "GEOGRAPHIC & SPATIAL INSTRUCTIONS" in block
        assert "SINGLE CITY" in block

    def test_geo_anchor_string(self):
        block = build_geo_prompt_block(geo_anchor="Tempelhof Airport")
        assert "Tempelhof Airport" in block
        assert "ANCHOR RULES" in block

    def test_geo_anchor_list(self):
        block = build_geo_prompt_block(geo_anchor=["Tempelhof Airport", "Checkpoint Charlie"])
        assert "Tempelhof Airport" in block
        assert "Checkpoint Charlie" in block

    def test_mobility_fixed_site(self):
        block = build_geo_prompt_block(mobility_mode="fixed_site")
        assert "FIXED-SITE MODE" in block
        assert "claustrophobia" in block

    def test_mobility_route_based(self):
        block = build_geo_prompt_block(mobility_mode="route_based")
        assert "ROUTE-BASED MODE" in block
        assert "timing" in block

    def test_mobility_multi_site(self):
        block = build_geo_prompt_block(mobility_mode="multi_site")
        assert "MULTI-SITE MODE" in block
        assert "2–4" in block

    def test_mobility_theater_wide(self):
        block = build_geo_prompt_block(mobility_mode="theater_wide")
        assert "THEATER-WIDE MODE" in block

    def test_all_params_combined(self):
        block = build_geo_prompt_block(
            geo_scope="country",
            geo_anchor="Berlin Wall",
            mobility_mode="multi_site",
        )
        assert "country" in block.lower()
        assert "Berlin Wall" in block
        assert "MULTI-SITE MODE" in block

    def test_contains_accuracy_constraints(self):
        block = build_geo_prompt_block(geo_scope="theater")
        assert "historical accuracy" in block

    def test_all_scope_values_have_guidance(self):
        for scope in GEO_SCOPE_VALUES:
            block = build_geo_prompt_block(geo_scope=scope)
            assert "GEOGRAPHIC & SPATIAL INSTRUCTIONS" in block

    def test_all_mobility_values_have_guidance(self):
        for mode in MOBILITY_MODE_VALUES:
            block = build_geo_prompt_block(mobility_mode=mode)
            assert "GEOGRAPHIC & SPATIAL INSTRUCTIONS" in block


# ═══════════════════════════════════════════════════════════════
# Planning Metadata
# ═══════════════════════════════════════════════════════════════


class TestBuildPlanningMetadata:
    def test_nothing_returns_empty(self):
        assert build_planning_metadata() == ""

    def test_lenses_shown(self):
        lenses = resolve_lenses("medics,logistics")
        meta = build_planning_metadata(lenses=lenses)
        assert "Active lenses" in meta
        assert "medics" in meta
        assert "logistics" in meta

    def test_geo_shown(self):
        meta = build_planning_metadata(geo_scope="theater", geo_anchor="Omaha Beach")
        assert "Geo scope: theater" in meta
        assert "Omaha Beach" in meta

    def test_mobility_shown(self):
        meta = build_planning_metadata(mobility_mode="route_based")
        assert "Mobility mode: route_based" in meta


# ═══════════════════════════════════════════════════════════════
# Backward Compatibility
# ═══════════════════════════════════════════════════════════════


class TestBackwardCompatibility:
    """When no lens/geo/mobility params are set, zero prompt impact."""

    def test_lens_block_zero_impact(self):
        assert build_lens_prompt_block([], 0.6) == ""

    def test_geo_block_zero_impact(self):
        assert build_geo_prompt_block(None, None, None) == ""

    def test_metadata_zero_impact(self):
        assert build_planning_metadata(None, None, None, None) == ""

    def test_resolve_none_zero_impact(self):
        assert resolve_lenses(None) == []
