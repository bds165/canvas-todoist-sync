"""Config loader: the non-secret YAML settings plus the two secret environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml


@dataclass(frozen=True)
class Config:
    todoist_project_name: str = "School"
    course_allowlist: frozenset[str] = frozenset()
    course_name_overrides: dict[str, str] = field(default_factory=dict)
    lookahead_days: int = 31
    lookback_days: int = 5
    sync_end_date: date = date(2027, 8, 1)
    dry_run: bool = False
    # Whose calendar days count: date-only Canvas Due Dates and dates written to Todoist.
    timezone: ZoneInfo = ZoneInfo("Pacific/Auckland")


@dataclass(frozen=True)
class Secrets:
    calendar_feed_url: str = field(repr=False)
    todoist_token: str = field(repr=False)


class ConfigError(Exception):
    pass


def load_config(path: Path) -> Config:
    """Settings from the YAML file, with the spec's defaults for anything missing."""
    raw: Any = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must be a mapping of settings")
    unknown = set(raw) - set(Config.__dataclass_fields__)
    if unknown:
        raise ConfigError(f"Unknown settings in {path}: {', '.join(sorted(unknown))}")

    defaults = Config()
    dry_run = raw.get("dry_run", defaults.dry_run)
    if not isinstance(dry_run, bool):
        raise ConfigError(f"dry_run in {path} must be true or false")
    try:
        tz = ZoneInfo(raw["timezone"]) if "timezone" in raw else defaults.timezone
    except (ZoneInfoNotFoundError, ValueError):
        raise ConfigError(f"Unknown timezone in {path}: {raw['timezone']!r}") from None
    sync_end_date = raw.get("sync_end_date", defaults.sync_end_date)
    if isinstance(sync_end_date, str):
        sync_end_date = date.fromisoformat(sync_end_date)
    return Config(
        todoist_project_name=str(raw.get("todoist_project_name", defaults.todoist_project_name)),
        course_allowlist=frozenset(str(c) for c in raw.get("course_allowlist") or []),
        course_name_overrides={
            str(k): str(v) for k, v in (raw.get("course_name_overrides") or {}).items()
        },
        lookahead_days=int(raw.get("lookahead_days", defaults.lookahead_days)),
        lookback_days=int(raw.get("lookback_days", defaults.lookback_days)),
        sync_end_date=sync_end_date,
        dry_run=dry_run,
        timezone=tz,
    )


def load_secrets(env: Mapping[str, str] = os.environ, dotenv: Path = Path(".env")) -> Secrets:
    """Secrets from the environment, falling back to a git-ignored .env file."""
    values = dict(_read_dotenv(dotenv)) if dotenv.exists() else {}
    values.update({k: v for k, v in env.items() if v})
    missing = [k for k in ("CANVAS_CALENDAR_FEED_URL", "TODOIST_TOKEN") if not values.get(k)]
    if missing:
        raise ConfigError(f"Missing secret(s): {', '.join(missing)}")
    return Secrets(values["CANVAS_CALENDAR_FEED_URL"], values["TODOIST_TOKEN"])


def _read_dotenv(path: Path) -> list[tuple[str, str]]:
    pairs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        pairs.append((key.strip(), value.strip().strip("\"'")))
    return pairs
