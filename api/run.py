"""ASGI entry point for running the API server.

Usage:
    uvicorn api.run:app --reload --port 8000
"""

from api.server import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn

    from api.config import get_api_config

    config = get_api_config()
    uvicorn.run(
        "api.server:app",
        host=config.host,
        port=config.port,
        reload=True,
        log_level="info",
    )
