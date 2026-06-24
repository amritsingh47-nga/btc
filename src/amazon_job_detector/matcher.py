"""Decide whether a job matches the user's criteria."""

from __future__ import annotations

from .config import MatchConfig
from .models import Job


def matches(job: Job, criteria: MatchConfig) -> bool:
    """Return True if ``job`` satisfies the configured criteria.

    Location is an OR across the three location filters (a job at SMF1 or SMF6
    qualifies if it hits ANY of them):
      * postal_codes: job's ZIP is in the list  (most reliable for a specific
        building — e.g. SMF1=95835, SMF6=95837).
      * cities: job's city is in the list.
      * site_codes: a code appears anywhere in the posting text. Note Amazon's
        search results usually carry only city/ZIP, not the FC code, so this
        rarely fires on its own — prefer postal_codes.

    The remaining filters are ANDed on top:
      * title_contains: at least ONE phrase appears in the title.
      * keywords: at least ONE keyword appears anywhere in the job.
      * min_pay_rate: job pay rate is known and >= the minimum.
    """
    blob = job.search_blob()

    if criteria.has_location_filter:
        location_hit = (
            any(code in blob for code in criteria.site_codes)
            or (job.postal_code and job.postal_code.lower() in criteria.postal_codes)
            or (job.city and job.city.lower() in criteria.cities)
        )
        if not location_hit:
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
