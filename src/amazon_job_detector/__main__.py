"""CLI entrypoint.

Usage:
    python -m amazon_job_detector run    [--config config.yaml]
    python -m amazon_job_detector once   [--config config.yaml]   # single poll, then exit
    python -m amazon_job_detector probe  [--config config.yaml]   # dump raw API response
    python -m amazon_job_detector test-notify [--config config.yaml]  # send a fake match
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from .amazon_source import AmazonHiringSource
from .config import ConfigError, load_config
from .matcher import matches
from .models import Job
from .notifiers import build_notifiers, notify_all
from .runner import run_forever, run_once
from .state import SeenStore


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="amazon_job_detector")
    parser.add_argument("command", choices=["run", "once", "probe", "test-notify"])
    parser.add_argument("--config", "-c", default="config.yaml")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)

    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 2

    if args.command == "probe":
        source = AmazonHiringSource(cfg.source)
        data = source.fetch_raw()
        print(json.dumps(data, indent=2, default=str))
        jobs = source.fetch()
        print(f"\n--- Normalized {len(jobs)} job(s); {sum(matches(j, cfg.match) for j in jobs)} match criteria ---", file=sys.stderr)
        return 0

    if args.command == "test-notify":
        fake = Job(
            job_id="TEST-123",
            title="Fulfillment Center Warehouse Associate",
            location_name="SMF1",
            city="Sacramento",
            state="CA",
            pay_rate=20.50,
            url="https://hiring.amazon.com/app#/jobDetail?jobId=TEST-123",
        )
        notify_all(build_notifiers(cfg.notify), fake)
        print("Sent test notification to all configured channels.")
        return 0

    if args.command == "once":
        source = AmazonHiringSource(cfg.source)
        store = SeenStore(cfg.state_file)
        n = run_once(source, cfg, store, build_notifiers(cfg.notify))
        print(f"Done. {n} new match(es).")
        return 0

    # run
    try:
        run_forever(cfg)
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
