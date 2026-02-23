"""FastAPI application — HTTP + SSE API for the History Tales pipeline."""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from api.config import get_api_config
from api.pipeline_runner import run_pipeline
from api.schemas import GenerateRequest, HealthResponse, RunDetail, RunSummary
from api.store import run_store

config = get_api_config()

app = FastAPI(
    title="History Tales Script Generator API",
    description="AI-powered documentary script generation with real-time progress streaming",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health and model configuration."""
    from history_tales_agent.config import get_config

    cfg = get_config()
    return HealthResponse(
        status="ok",
        version="1.0.0",
        pipeline_nodes=16,
        models={
            "creative": cfg.openai_model,
            "fast": cfg.openai_fast_model or cfg.openai_model,
        },
    )


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------


@app.post("/generate", response_model=dict)
async def generate_script(request: GenerateRequest):
    """Start a new pipeline run. Returns the run_id immediately.

    Use GET /runs/{run_id}/stream to receive real-time SSE progress events.
    Use GET /runs/{run_id} to fetch the completed result.
    """
    params = request.model_dump()
    run_id = run_store.create_run(params)

    # Fire-and-forget the pipeline in background — store the task handle
    task = asyncio.create_task(run_pipeline(run_id, params))
    run_store.set_task(run_id, task)

    return {
        "run_id": run_id,
        "status": "running",
        "message": "Pipeline started. Stream progress at /runs/{run_id}/stream",
        "stream_url": f"/runs/{run_id}/stream",
        "result_url": f"/runs/{run_id}",
    }


# ---------------------------------------------------------------------------
# SSE Stream
# ---------------------------------------------------------------------------


@app.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    """Stream real-time pipeline progress via Server-Sent Events.

    Events:
        - node_progress: A node started/completed
        - complete: Pipeline finished
        - error: Pipeline failed
    """
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    async def event_generator():
        # First, send any events that already happened (late join support)
        past_events = run_store.get_events(run_id)
        for event in past_events:
            yield {
                "event": "node_progress",
                "data": event.model_dump_json(),
            }

        # If already completed, send final event and close
        current_run = run_store.get_run(run_id)
        if current_run and current_run.status in ("completed", "failed", "cancelled"):
            yield {
                "event": current_run.status,
                "data": json.dumps({"run_id": run_id, "status": current_run.status}),
            }
            return

        # Subscribe to live events
        queue = run_store.subscribe(run_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=120.0)
                    event_type = "node_progress"
                    if event.node == "__complete__":
                        event_type = "complete"
                    elif event.node in ("__error__", "__cancelled__"):
                        event_type = "error" if event.node == "__error__" else "cancelled"

                    yield {
                        "event": event_type,
                        "data": event.model_dump_json(),
                    }

                    # Close stream after terminal events
                    if event_type in ("complete", "error", "cancelled"):
                        return
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {"event": "ping", "data": ""}
        finally:
            run_store.unsubscribe(run_id, queue)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


@app.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    """Cancel a running pipeline."""
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    if run.status != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Run {run_id} is not running (status: {run.status})",
        )

    success = run_store.cancel_run(run_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to cancel run")

    return {"run_id": run_id, "status": "cancelled", "message": "Cancellation requested"}


# ---------------------------------------------------------------------------
# Run CRUD
# ---------------------------------------------------------------------------


@app.get("/runs", response_model=list[RunSummary])
async def list_runs(limit: int = 20):
    """List recent pipeline runs."""
    return run_store.list_runs(limit=limit)


@app.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: str):
    """Get full details of a pipeline run."""
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


@app.get("/runs/{run_id}/export/script")
async def export_script(run_id: str):
    """Export the final script as markdown."""
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    if not run.final_script:
        raise HTTPException(status_code=400, detail="No script available yet")

    from fastapi.responses import PlainTextResponse

    title = run.title or "Untitled"
    content = f"# {title}\n\n{run.final_script}"
    return PlainTextResponse(
        content=content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{title.replace(" ", "_")}_script.md"'
        },
    )


@app.get("/runs/{run_id}/export/sources")
async def export_sources(run_id: str):
    """Export the sources & claims log as JSON."""
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    from fastapi.responses import JSONResponse

    return JSONResponse(
        content={
            "run_id": run_id,
            "title": run.title,
            "sources": run.sources_log,
            "claims": run.claims,
        }
    )
