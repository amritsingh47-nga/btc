"""Decide whether a job matches the user's criteria."""

from __future__ import annotations

from .config import MatchConfig
from .models import Job


def matches(job: Job, criteria: MatchConfig) -> bool:
    """Return True if ``job`` satisfies every configured criterion.

    Rules (all that are configured must pass — AND semantics):
      * site_codes: at least ONE configured code appears anywhere in the job
        (title/location/raw payload). This is the SMF1/SMF6 filter.
      * title_contains: at least ONE phrase appears in the title.
      * keywords: at least ONE keyword appears anywhere in the job.
      * min_pay_rate: job pay rate is known and >= the minimum.
    """
    blob = job.search_blob()

    if criteria.site_codes and not any(code in blob for code in criteria.site_codes):
        return False

    if criteria.title_contains:
        title = job.title.lower()
        if not any(phrase in title for phrase in criteria.title_contains):
            return False

    if criteria.keywords and not any(kw in blob for kw in criteria.keywords):
        return False

    if criteria.min_pay_rate is not None:
        if job.pay_rate is None or job.pay_rate < criteria.min_pay_rate:
            return False

    return True
