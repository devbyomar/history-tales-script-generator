"""In-memory run store — tracks active and completed pipeline runs.

In production, replace with Supabase/PostgreSQL persistence.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from api.schemas import NodeProgress, RunDetail, RunSummary


class RunStore:
    """Thread-safe in-memory store for pipeline runs."""

    def __init__(self) -> None:
        self._runs: dict[str, RunDetail] = {}
        self._events: dict[str, list[NodeProgress]] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def create_run(self, params: dict[str, Any]) -> str:
        """Create a new run entry and return its ID."""
        run_id = uuid4().hex[:12]
        now = datetime.utcnow().isoformat()

        run = RunDetail(
            run_id=run_id,
            status="running",
            created_at=now,
            video_length_minutes=params["video_length_minutes"],
            era_focus=params.get("era_focus"),
            geo_focus=params.get("geo_focus"),
            topic_seed=params.get("topic_seed"),
            tone=params.get("tone", "cinematic-serious"),
        )
        self._runs[run_id] = run
        self._events[run_id] = []
        self._subscribers[run_id] = []
        return run_id

    def get_run(self, run_id: str) -> Optional[RunDetail]:
        return self._runs.get(run_id)

    def list_runs(self, limit: int = 20) -> list[RunSummary]:
        """Return most recent runs as summaries."""
        runs = sorted(
            self._runs.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )[:limit]
        return [RunSummary(**r.model_dump(exclude={"final_script", "sources_log", "claims", "qc_report", "errors"})) for r in runs]

    def update_run(self, run_id: str, **kwargs: Any) -> None:
        """Update fields on an existing run."""
        run = self._runs.get(run_id)
        if not run:
            return
        for key, value in kwargs.items():
            if hasattr(run, key):
                setattr(run, key, value)

    async def publish_event(self, event: NodeProgress) -> None:
        """Publish a node progress event to all subscribers."""
        run_id = event.run_id
        if run_id in self._events:
            self._events[run_id].append(event)
        for queue in self._subscribers.get(run_id, []):
            await queue.put(event)

    def subscribe(self, run_id: str) -> asyncio.Queue:
        """Subscribe to SSE events for a run. Returns an asyncio Queue."""
        queue: asyncio.Queue = asyncio.Queue()
        if run_id not in self._subscribers:
            self._subscribers[run_id] = []
        self._subscribers[run_id].append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        if run_id in self._subscribers:
            self._subscribers[run_id] = [
                q for q in self._subscribers[run_id] if q is not queue
            ]

    def get_events(self, run_id: str) -> list[NodeProgress]:
        """Get all events for a run (for late-joining clients)."""
        return self._events.get(run_id, [])


# Singleton
run_store = RunStore()
