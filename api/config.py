"""API server configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class APIConfig:
    """Configuration for the FastAPI server."""

    # Server
    host: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv(
            "CORS_ORIGINS", "http://localhost:3000"
        ).split(",")
    )

    # Supabase (optional — for persistent storage)
    supabase_url: str = field(
        default_factory=lambda: os.getenv("SUPABASE_URL", "")
    )
    supabase_key: str = field(
        default_factory=lambda: os.getenv("SUPABASE_ANON_KEY", "")
    )

    # Auth (optional — for multi-user)
    jwt_secret: str = field(
        default_factory=lambda: os.getenv("JWT_SECRET", "dev-secret-change-me")
    )
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)


def get_api_config() -> APIConfig:
    return APIConfig()
