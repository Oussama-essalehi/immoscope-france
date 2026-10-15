"""Shared configuration, paths and logging helpers for the DVF pipeline."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


@lru_cache(maxsize=1)
def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Load ``config.yaml`` once and return it as a dictionary."""
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def project_path(key: str) -> Path:
    """Return an absolute path from the ``paths`` section, creating it if needed."""
    path = PROJECT_ROOT / load_config()["paths"][key]
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class DatabaseSettings:
    """Connection settings for PostgreSQL, overridable by environment variables."""

    host: str
    port: int
    name: str
    user: str
    password: str
    schema: str

    @classmethod
    def from_config(cls) -> "DatabaseSettings":
        cfg = load_config()["database"]
        return cls(
            host=os.getenv("DVF_DB_HOST", cfg["host"]),
            port=int(os.getenv("DVF_DB_PORT", cfg["port"])),
            name=os.getenv("DVF_DB_NAME", cfg["name"]),
            user=os.getenv("DVF_DB_USER", cfg["user"]),
            password=os.getenv("DVF_DB_PASSWORD", cfg["password"]),
            schema=cfg["schema"],
        )

    @property
    def url(self) -> str:
        """SQLAlchemy URL using the psycopg (v3) driver."""
        return (
            f"postgresql+psycopg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


def setup_logging(level: int = logging.INFO) -> None:
    """Configure a concise, timestamped log format for every pipeline step."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
