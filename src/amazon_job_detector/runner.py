"""The polling loop that ties source -> matcher -> state -> notifiers together."""

from __future__ import annotations

import logging
import random
import time

import requests

from .amazon_source import AmazonHiringSource
from .config import Config
from .matcher import matches
from .notifiers import build_notifiers, notify_all
from .state import SeenStore

log = logging.getLogger(__name__)


def run_once(
    source: AmazonHiringSource,
    cfg: Config,
    store: SeenStore,
    notifiers,
) -> int:
    """One poll cycle. Returns the number of fresh matches alerted on."""
    jobs = source.fetch()
    fresh = 0
    for job in jobs:
        if not matches(job, cfg.match):
            continue
        if not store.is_new(job.job_id):
            continue
        log.info("MATCH: %s (%s) [%s]", job.title, job.job_id, job.location_name)
        notify_all(notifiers, job)
        store.mark(job.job_id)
        fresh += 1
    if fresh:
        store.save()
    return fresh


def run_forever(cfg: Config) -> None:
    source = AmazonHiringSource(cfg.source)
    store = SeenStore(cfg.state_file)
    notifiers = build_notifiers(cfg.notify)

    if not cfg.match.has_location_filter and not cfg.match.title_contains and not cfg.match.keywords:
        log.warning("No match criteria configured — EVERY job will alert. Set match.postal_codes.")

    log.info(
        "Watching for jobs in %s every ~%ds (+/-%ds). Notifiers: %s",
        cfg.match.postal_codes or cfg.match.cities or cfg.match.site_codes or "(any)",
        cfg.poll_interval_seconds,
        cfg.jitter_seconds,
        [type(n).__name__ for n in notifiers],
    )

    consecutive_errors = 0
    while True:
        try:
            n = run_once(source, cfg, store, notifiers)
            consecutive_errors = 0
            if n:
                log.info("Alerted on %d new match(es).", n)
        except requests.HTTPError as e:
            consecutive_errors += 1
            code = e.response.status_code if e.response is not None else "?"
            log.error("HTTP %s from API (attempt %d). Token may be expired — see README.", code, consecutive_errors)
        except Exception:  # noqa: BLE001
            consecutive_errors += 1
            log.exception("poll failed (attempt %d)", consecutive_errors)

        # Back off when the API is unhappy so we don't hammer it (and get blocked).
        base = cfg.poll_interval_seconds
        if consecutive_errors:
            base = min(base * (2 ** consecutive_errors), 600)
        sleep_for = base + random.uniform(0, cfg.jitter_seconds)
        time.sleep(sleep_for)
