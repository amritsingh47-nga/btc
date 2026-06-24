"""Client for the hiring.amazon.com hourly-jobs search API.

IMPORTANT — read this before debugging "no jobs found":

hiring.amazon.com is a single-page app backed by an AWS AppSync GraphQL API.
Amazon does NOT publish this API, and it changes without notice:

  * the endpoint host can rotate,
  * the request requires a session ``Authorization`` token tied to your login,
  * there is bot/rate-limit protection.

So this client is deliberately *configurable*. The defaults below match the
well-known public shape of the ``searchJobCardsByLocation`` query, but if Amazon
changes things you update ``config.yaml`` (endpoint / auth token / query_override)
and the field map here — no need to rewrite the loop. Use ``--probe`` to dump a
raw response and see exactly what the live API returns today.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from .config import SourceConfig
from .models import Job

log = logging.getLogger(__name__)

# The well-known GraphQL query used by the hiring.amazon.com job-search UI.
# Kept minimal/robust; override via config.source.query_override if the schema shifts.
DEFAULT_QUERY = """
query searchJobCardsByLocation($searchJobRequest: SearchJobRequest!) {
  searchJobCardsByLocation(searchJobRequest: $searchJobRequest) {
    nextToken
    jobCards {
      jobId
      jobTitle
      city
      state
      locationName
      totalPayRateMin
      totalPayRateMax
      currencyCode
      scheduleCount
    }
  }
}
""".strip()


class AmazonHiringSource:
    """Fetches and normalizes hourly job cards near a geo point."""

    def __init__(self, cfg: SourceConfig):
        self.cfg = cfg
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://hiring.amazon.com",
                "Referer": "https://hiring.amazon.com/app",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                "country": "US",
            }
        )
        if cfg.auth_token:
            # AppSync accepts the session token via the Authorization header.
            self.session.headers["Authorization"] = cfg.auth_token

    def _build_payload(self) -> dict[str, Any]:
        return {
            "operationName": "searchJobCardsByLocation",
            "query": self.cfg.query_override or DEFAULT_QUERY,
            "variables": {
                "searchJobRequest": {
                    "locale": self.cfg.locale,
                    "country": self.cfg.country,
                    "keyWords": "",
                    "equalFilters": [],
                    "containFilters": [{"key": "isPrivateSchedule", "val": ["false"]}],
                    "rangeFilters": [],
                    "orFilters": [],
                    "dateFilters": [],
                    "sorters": [],
                    "pageSize": self.cfg.page_size,
                    "consolidateSchedule": True,
                    "geoQueryClause": {
                        "lat": self.cfg.geo.lat,
                        "lng": self.cfg.geo.lng,
                        "unit": "mi",
                        "distance": self.cfg.geo.distance_miles,
                    },
                }
            },
        }

    def fetch_raw(self) -> dict[str, Any]:
        """Return the raw JSON response (used by --probe and by fetch())."""
        resp = self.session.post(
            self.cfg.endpoint,
            json=self._build_payload(),
            timeout=self.cfg.timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data and data["errors"]:
            raise RuntimeError(f"GraphQL errors: {data['errors']}")
        return data

    def fetch(self) -> list[Job]:
        """Fetch current job cards and normalize them into Job objects."""
        data = self.fetch_raw()
        cards = (
            (data.get("data") or {})
            .get("searchJobCardsByLocation", {})
            .get("jobCards")
            or []
        )
        jobs: list[Job] = []
        for c in cards:
            job_id = str(c.get("jobId") or c.get("id") or "")
            if not job_id:
                continue
            pay = c.get("totalPayRateMin") or c.get("payRateMin")
            jobs.append(
                Job(
                    job_id=job_id,
                    title=c.get("jobTitle") or c.get("title") or "",
                    location_name=c.get("locationName") or "",
                    city=c.get("city") or "",
                    state=c.get("state") or "",
                    pay_rate=float(pay) if pay not in (None, "") else None,
                    url=f"https://hiring.amazon.com/app#/jobDetail?jobId={job_id}&locale={self.cfg.locale}",
                    raw=c,
                )
            )
        log.debug("fetched %d job cards", len(jobs))
        return jobs
