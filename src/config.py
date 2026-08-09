"""Application configuration: `config.yaml` defaults, overridable by environment.

Precedence is **environment wins, YAML falls back**. That ordering is the point:
`config.yaml` is committed and holds the values that are correct for local
development, while a deployed container must be able to set `DATABASE_URL`,
`CORS_ALLOWED_ORIGINS`, etc. without rebuilding an image or editing a tracked
file (see docs/prod_roadmap/production-roadmap.md §5).

Implementation note: pydantic-settings ranks init kwargs *above* env vars, so
loading YAML straight into `Config(**raw)` would invert the precedence we want.
`load_config()` therefore drops any YAML key that is already supplied by the
environment (or by a `.env` file) and lets the settings sources fill it in —
which also means env values get pydantic's parsing/validation for free.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

import yaml
from dotenv import dotenv_values
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_CONFIG_PATH = "config.yaml"
DEFAULT_ENV_FILE = ".env"


class Config(BaseSettings):
    # Env var names are the field names upper-cased with no prefix
    # (ANCHORS, LOOKBACK_DAYS, CORS_ALLOWED_ORIGINS, ...), matching the
    # variable table in production-roadmap.md §9.2.
    model_config = SettingsConfigDict(env_file=DEFAULT_ENV_FILE, extra="ignore")

    # `NoDecode` opts these out of pydantic-settings' default "complex fields
    # are JSON" rule so the validator below can accept plain comma-separated
    # env values (ANCHORS=NVDA,AAPL) — far friendlier to type into a hosting
    # dashboard than '["NVDA","AAPL"]'. JSON still works.
    anchors: Annotated[list[str], NoDecode]
    lookback_days: int
    top_n: int
    correlation_threshold: float
    rolling_window: int
    data_dir: Path
    outputs_dir: Path
    market_proxy_ticker: str
    lag_max_days: int
    regime_recent_days: int
    regime_break_threshold: float
    price_cache_ttl_seconds: float
    cors_allowed_origins: Annotated[list[str], NoDecode]

    # Deployment settings — no YAML defaults, because they are environment
    # specific (and DATABASE_URL is a secret that must never be committed).
    # `database_url` is unused until the Phase 4.8 Postgres cutover, which
    # keys off its presence in src/api/deps.py.
    database_url: str | None = None
    log_level: str = "INFO"

    @field_validator("anchors", "cors_allowed_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            # `NoDecode` means nothing else will parse a JSON list for us, so
            # accept both spellings here.
            if stripped.startswith("["):
                return json.loads(stripped)
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        return value.upper()


def _env_supplied_fields(env_file: Path) -> set[str]:
    """Field names whose value is already coming from the environment.

    Includes keys from the `.env` file, since pydantic-settings treats those as
    a settings source too — without this they would lose to the YAML defaults.
    """
    present = {key.upper() for key in os.environ}
    if env_file.is_file():
        present |= {key.upper() for key, val in dotenv_values(env_file).items() if val is not None}
    return {name for name in Config.model_fields if name.upper() in present}


def load_config(
    path: str | Path | None = None,
    env_file: str | Path = DEFAULT_ENV_FILE,
) -> Config:
    """Build a `Config` from YAML defaults plus environment overrides.

    `CONFIG_PATH` overrides the YAML location, which lets a container mount a
    different file without a code change. A missing YAML file is not an error
    (a fully env-configured deployment is valid) — but a field that ends up
    with no value from either source still raises, so misconfiguration fails
    fast at startup rather than at first request.
    """
    yaml_path = Path(os.environ.get("CONFIG_PATH") or path or DEFAULT_CONFIG_PATH)
    raw: dict[str, Any] = {}
    if yaml_path.is_file():
        with open(yaml_path) as f:
            raw = yaml.safe_load(f) or {}

    overridden = _env_supplied_fields(Path(env_file))
    defaults = {key: value for key, value in raw.items() if key not in overridden}
    return Config(**defaults)
