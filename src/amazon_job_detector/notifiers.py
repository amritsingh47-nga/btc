"""Pluggable alert channels. Add a new channel by implementing Notifier.send()."""

from __future__ import annotations

import logging
from typing import Protocol

import requests

from .config import NotifyConfig
from .models import Job

log = logging.getLogger(__name__)


def format_job(job: Job) -> str:
    bits = [f"\U0001f6a8 Amazon job match: {job.title or 'Untitled role'}"]
    loc = ", ".join(p for p in [job.location_name, job.city, job.state] if p)
    if loc:
        bits.append(f"\U0001f4cd {loc}")
    if job.pay_rate is not None:
        bits.append(f"\U0001f4b5 ${job.pay_rate:.2f}/hr")
    if job.url:
        bits.append(f"\U0001f517 {job.url}")
    return "\n".join(bits)


class Notifier(Protocol):
    def send(self, job: Job) -> None: ...


class ConsoleNotifier:
    def send(self, job: Job) -> None:
        print("\n" + "=" * 60)
        print(format_job(job))
        print("=" * 60, flush=True)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.chat_id = chat_id

    def send(self, job: Job) -> None:
        resp = requests.post(
            self.url,
            json={"chat_id": self.chat_id, "text": format_job(job), "disable_web_page_preview": False},
            timeout=15,
        )
        resp.raise_for_status()


class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, job: Job) -> None:
        resp = requests.post(self.webhook_url, json={"content": format_job(job)}, timeout=15)
        resp.raise_for_status()


def build_notifiers(cfg: NotifyConfig) -> list[Notifier]:
    notifiers: list[Notifier] = []
    if cfg.console:
        notifiers.append(ConsoleNotifier())
    if cfg.telegram:
        notifiers.append(TelegramNotifier(cfg.telegram.bot_token, cfg.telegram.chat_id))
    if cfg.discord:
        notifiers.append(DiscordNotifier(cfg.discord.webhook_url))
    return notifiers


def notify_all(notifiers: list[Notifier], job: Job) -> None:
    """Send to every channel; one channel failing must not block the others."""
    for n in notifiers:
        try:
            n.send(job)
        except Exception:  # noqa: BLE001 - alerting must be resilient
            log.exception("notifier %s failed for job %s", type(n).__name__, job.job_id)
