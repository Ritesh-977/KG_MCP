"""Application settings via pydantic-settings (env + defaults)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from env / .env.

    All Neo4j connection details, the repos working directory, and ingestion
    tuning knobs live here. Defaults match the bundled ``.env.example``.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme123"
    neo4j_db: str = "neo4j"
    repos_dir: Path = Path("./repos")
    ingest_batch_size: int = 200
    ingest_depth: int = 1
    log_level: str = "INFO"
