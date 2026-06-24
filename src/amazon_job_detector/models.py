"""Normalized data models shared across the detector."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Job:
    """A single normalized job posting.

    Only a handful of fields are guaranteed; ``raw`` keeps the original payload
    so matching/notification can reach into provider-specific fields and so the
    --probe command can show you exactly what the API returned.
    """

    job_id: str
    title: str = ""
    location_name: str = ""
    city: str = ""
    state: str = ""
    pay_rate: float | None = None
    url: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def search_blob(self) -> str:
        """Lowercased text used for substring matching (title + location).

        Includes the raw payload as a fallback so site codes like ``SMF1`` are
        found even when they only appear in a nested field we didn't map.
        """
        import json

        parts = [self.title, self.location_name, self.city, self.state]
        try:
            parts.append(json.dumps(self.raw, default=str))
        except (TypeError, ValueError):
            pass
        return " ".join(p for p in parts if p).lower()
