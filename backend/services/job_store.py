from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RenderJob:
    id: str
    status: str = "queued"  # queued, analyzing, rendering, encoding, done, failed
    progress: float = 0.0
    message: str = "Waiting to start"
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["age_seconds"] = round(time.time() - self.created_at, 1)
        data["progress"] = round(max(0.0, min(100.0, self.progress)), 1)
        return data


class JobStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, RenderJob] = {}

    def create(self, job_id: str) -> RenderJob:
        with self._lock:
            job = RenderJob(id=job_id)
            self._jobs[job_id] = job
            self._cleanup_locked()
            return job

    def update(self, job_id: str, *, status: str | None = None, progress: float | None = None, message: str | None = None, result: dict[str, Any] | None = None, error: str | None = None) -> None:
        with self._lock:
            job = self._jobs.setdefault(job_id, RenderJob(id=job_id))
            if status is not None:
                job.status = status
            if progress is not None:
                job.progress = max(0.0, min(100.0, progress))
            if message is not None:
                job.message = message
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            job.updated_at = time.time()

    def get(self, job_id: str) -> RenderJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def recent(self) -> list[dict[str, Any]]:
        with self._lock:
            return [job.to_dict() for job in sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)[:30]]

    def _cleanup_locked(self) -> None:
        now = time.time()
        stale = [job_id for job_id, job in self._jobs.items() if now - job.created_at > 24 * 3600]
        for job_id in stale:
            self._jobs.pop(job_id, None)
