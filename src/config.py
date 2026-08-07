"""Load config.yaml + .env into a single settings object."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    raw: dict[str, Any]
    project_root: Path = PROJECT_ROOT

    github_token: str | None = None
    searxng_base_url_override: str | None = None

    def __post_init__(self) -> None:
        self.github_token = os.getenv("GITHUB_TOKEN") or None
        self.searxng_base_url_override = os.getenv("SEARXNG_BASE_URL") or None

    # -- convenience accessors -------------------------------------------------
    @property
    def target_companies(self) -> list[str]:
        return list(self.raw.get("target_companies", []))

    @property
    def target_roles(self) -> list[str]:
        return list(self.raw.get("target_roles", []))

    @property
    def exclude_title_keywords(self) -> list[str]:
        return [k.lower() for k in self.raw.get("exclude_title_keywords", [])]

    @property
    def run_config(self) -> dict[str, Any]:
        return dict(self.raw.get("run", {}))

    def source_config(self, name: str) -> dict[str, Any]:
        cfg = dict(self.raw.get("sources", {}).get(name, {}))
        if name == "searxng_search" and self.searxng_base_url_override:
            cfg["base_url"] = self.searxng_base_url_override
        return cfg

    def path(self, key: str) -> Path:
        rel = self.raw["paths"][key]
        p = self.project_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


def load_settings(config_path: str | Path = PROJECT_ROOT / "config.yaml") -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return Settings(raw=raw)
