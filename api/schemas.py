"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    """Request body for the /generate endpoint."""

    video_length_minutes: int = Field(..., ge=5, le=60, description="Target video length in minutes")
    era_focus: Optional[str] = Field(None, description="Historical era filter")
    geo_focus: Optional[str] = Field(None, description="Geographic focus")
    topic_seed: Optional[str] = Field(None, description="Starting topic idea")
    tone: str = Field("cinematic-serious", description="Narrative tone")
    sensitivity_level: str = Field("general audiences", description="Content sensitivity")
    nonlinear_open: bool = Field(True, description="Use nonlinear opening")
    previous_format_tag: Optional[str] = Field(None, description="Previous format for rotation")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class RunSummary(BaseModel):
    """Summary of a completed pipeline run."""

    run_id: str
    status: str  # "running" | "completed" | "failed" | "cancelled"
    created_at: str
    completed_at: Optional[str] = None

    # Input params
    video_length_minutes: int
    era_focus: Optional[str] = None
    geo_focus: Optional[str] = None
    topic_seed: Optional[str] = None
    tone: str = "cinematic-serious"

    # Results (populated on completion)
    title: Optional[str] = None
    format_tag: Optional[str] = None
    topic_score: Optional[float] = None
    word_count: Optional[int] = None
    target_words: Optional[int] = None
    emotional_intensity: Optional[float] = None
    sensory_density: Optional[float] = None
    source_count: Optional[int] = None
    claim_count: Optional[int] = None
    qc_pass: Optional[bool] = None
    qc_issues: list[str] = Field(default_factory=list)


class RunDetail(RunSummary):
    """Full detail of a pipeline run, including the script."""

    final_script: Optional[str] = None
    sources_log: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    qc_report: Optional[dict[str, Any]] = None
    errors: list[str] = Field(default_factory=list)


class NodeProgress(BaseModel):
    """SSE event payload for pipeline progress updates."""

    run_id: str
    node: str
    status: str  # "started" | "completed" | "failed"
    node_index: int  # 1-based position in pipeline
    total_nodes: int = 16
    message: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: Optional[dict[str, Any]] = None  # Optional extra data from node


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = "1.0.0"
    pipeline_nodes: int = 16
    models: dict[str, str] = Field(default_factory=dict)
