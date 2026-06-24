"""Persistent record of jobs we've already alerted on, so we don't double-notify.

Stored as a small JSON file. Entries expire after a TTL so the file doesn't grow
forever and so a posting that genuinely reappears later can re-alert.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


class SeenStore:
    def __init__(self, path: str | Path, ttl_seconds: int = 7 * 24 * 3600):
        self.path = Path(path)
        self.ttl_seconds = ttl_seconds
        self._seen: dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._seen = {k: float(v) for k, v in json.loads(self.path.read_text()).items()}
            except (ValueError, OSError):
                self._seen = {}
        self._prune()

    def _prune(self) -> None:
        cutoff = time.time() - self.ttl_seconds
        self._seen = {k: v for k, v in self._seen.items() if v >= cutoff}

    def is_new(self, job_id: str) -> bool:
        return job_id not in self._seen

    def mark(self, job_id: str) -> None:
        self._seen[job_id] = time.time()

    def save(self) -> None:
        self._prune()
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._seen))
        tmp.replace(self.path)
