"""Scan orchestration independent from the GUI."""

from __future__ import annotations

from dataclasses import dataclass, field
import copy
from datetime import datetime, timezone
from typing import Callable

from platforms import get_collector
from scoring.engine import evaluate


ProgressCallback = Callable[[int, str], None]


@dataclass
class ScanBundle:
    metrics: dict
    results: dict
    scanned_at: str
    deep_sections: list = field(default_factory=list)


class ScanService:
    def __init__(self, collector_factory=get_collector):
        self.collector_factory = collector_factory

    def scan(self, progress: ProgressCallback | None = None, deep: bool = False) -> ScanBundle:
        collector = self.collector_factory()

        # A deep scan adds a second, slower phase. Map the standard collection
        # onto the first 55% of the progress bar and the deep phase onto 55-100%.
        if deep and progress:
            base_progress = lambda pct, label: progress(int(pct * 0.55), label)
        else:
            base_progress = progress

        metrics = collector.collect(progress_callback=base_progress)

        deep_sections: list = []
        if deep:
            from core.deep_scan import collect_deep
            from scoring.deep import build_deep_sections
            deep_progress = (lambda pct, label: progress(55 + int(pct * 0.45), label)) if progress else None
            collect_deep(metrics, deep_progress)
            deep_sections = build_deep_sections(metrics)

        results: dict[str, dict] = {}
        for device in ("Desktop", "Laptop"):
            results[device] = {}
            for profile in ("Everyday", "Gaming", "Workstation"):
                results[device][profile] = evaluate(copy.deepcopy(metrics), profile, device == "Laptop")
        return ScanBundle(
            metrics=metrics,
            results=results,
            scanned_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            deep_sections=deep_sections,
        )
