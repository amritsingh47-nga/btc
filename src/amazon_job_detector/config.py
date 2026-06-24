"""Configuration loading.

Config lives in a YAML file; all secrets are referenced indirectly via the name
of an environment variable (``*_env`` keys) so tokens never sit in the YAML.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


def _env(var_name: str | None, *, required: bool = False, label: str = "") -> str | None:
    if not var_name:
        if required:
            raise ConfigError(f"{label}: no environment variable name configured")
        return None
    value = os.environ.get(var_name)
    if required and not value:
        raise ConfigError(
            f"{label}: environment variable {var_name!r} is not set. "
            f"Export it (or add it to your .env) before running."
        )
    return value


@dataclass
class GeoConfig:
    lat: float
    lng: float
    distance_miles: int = 50


@dataclass
class SourceConfig:
    endpoint: str
    auth_token: str | None
    geo: GeoConfig
    page_size: int = 100
    country: str = "United States"
    locale: str = "en-US"
    # Optional overrides for when the API schema changes (see README "Keeping it working").
    query_override: str | None = None
    timeout_seconds: int = 20


@dataclass
class MatchConfig:
    site_codes: list[str] = field(default_factory=list)
    title_contains: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    min_pay_rate: float | None = None

    def __post_init__(self) -> None:
        self.site_codes = [s.lower() for s in self.site_codes]
        self.title_contains = [s.lower() for s in self.title_contains]
        self.keywords = [s.lower() for s in self.keywords]


@dataclass
class TelegramConfig:
    bot_token: str
    chat_id: str


@dataclass
class DiscordConfig:
    webhook_url: str


@dataclass
class NotifyConfig:
    console: bool = True
    telegram: TelegramConfig | None = None
    discord: DiscordConfig | None = None


@dataclass
class Config:
    poll_interval_seconds: int
    jitter_seconds: int
    source: SourceConfig
    match: MatchConfig
    notify: NotifyConfig
    state_file: Path


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    data: dict[str, Any] = yaml.safe_load(path.read_text()) or {}

    src = data.get("source") or {}
    geo = src.get("geo") or {}
    if "lat" not in geo or "lng" not in geo:
        raise ConfigError("source.geo.lat and source.geo.lng are required")

    source = SourceConfig(
        endpoint=src.get("endpoint")
        or "https://e5mquma77feepi2bdn4d6h3mpu.appsync-api.us-east-1.amazonaws.com/graphql",
        auth_token=_env(src.get("auth_token_env"), label="source.auth_token_env"),
        geo=GeoConfig(
            lat=float(geo["lat"]),
            lng=float(geo["lng"]),
            distance_miles=int(geo.get("distance_miles", 50)),
        ),
        page_size=int(src.get("page_size", 100)),
        country=src.get("country", "United States"),
        locale=src.get("locale", "en-US"),
        query_override=src.get("query_override"),
        timeout_seconds=int(src.get("timeout_seconds", 20)),
    )

    m = data.get("match") or {}
    match = MatchConfig(
        site_codes=list(m.get("site_codes") or []),
        title_contains=list(m.get("title_contains") or []),
        keywords=list(m.get("keywords") or []),
        min_pay_rate=m.get("min_pay_rate"),
    )

    n = data.get("notify") or {}
    telegram = None
    if n.get("telegram"):
        t = n["telegram"]
        telegram = TelegramConfig(
            bot_token=_env(t.get("bot_token_env"), required=True, label="notify.telegram.bot_token_env") or "",
            chat_id=_env(t.get("chat_id_env"), required=True, label="notify.telegram.chat_id_env") or "",
        )
    discord = None
    if n.get("discord"):
        d = n["discord"]
        discord = DiscordConfig(
            webhook_url=_env(d.get("webhook_url_env"), required=True, label="notify.discord.webhook_url_env") or "",
        )
    notify = NotifyConfig(
        console=bool(n.get("console", True)),
        telegram=telegram,
        discord=discord,
    )

    return Config(
        poll_interval_seconds=int(data.get("poll_interval_seconds", 25)),
        jitter_seconds=int(data.get("jitter_seconds", 8)),
        source=source,
        match=match,
        notify=notify,
        state_file=Path(data.get("state_file", "seen_jobs.json")),
    )
