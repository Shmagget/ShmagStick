"""Shared, read-only collector orchestration."""

from __future__ import annotations

import abc
from collections.abc import Callable, Iterable
from typing import Any

from core.logging_config import configure_logging, safe_path
from core.models import (
    CategoryResult,
    CollectionWarning,
    Finding,
    ScanResult,
    Severity,
    Upgrade,
)


CollectorStep = tuple[str, str, Callable[[dict[str, Any]], None]]


class MetricCollector(abc.ABC):
    """Abstract base class for isolated, non-destructive diagnostic checks."""

    def __init__(self) -> None:
        self.logger = configure_logging().getChild(self.__class__.__name__)

    @abc.abstractmethod
    def collect(self, progress_callback=None) -> dict[str, Any]:
        """Run all metric collection and return a flat dict of measurements."""
        ...

    def _collect_steps(self, steps: Iterable[CollectorStep], progress_callback=None) -> dict[str, Any]:
        step_list = list(steps)
        metrics: dict[str, Any] = {"collection_warnings": [], "category_availability": {}}
        total = max(1, len(step_list))
        for index, (category, label, operation) in enumerate(step_list):
            if progress_callback:
                progress_callback(int(index / total * 100), label)
            try:
                operation(metrics)
                if category != "system":
                    metrics["category_availability"].setdefault(category, {
                        "available": True,
                        "reason": "",
                        "confidence": "Medium",
                    })
            except PermissionError as exc:
                self._record_failure(metrics, category, label, exc, True)
            except Exception as exc:
                self._record_failure(metrics, category, label, exc, False)

        self._finalize_availability(metrics)
        if progress_callback:
            progress_callback(100, "Finalizing results")
        return metrics

    def _record_failure(
        self,
        metrics: dict[str, Any],
        category: str,
        operation: str,
        exc: Exception,
        permission_related: bool,
    ) -> None:
        message = (
            "Permission was denied; run elevated for this optional check."
            if permission_related
            else "The check could not be completed on this system."
        )
        warning = CollectionWarning(category, operation, message, permission_related)
        metrics["collection_warnings"].append(warning.__dict__)
        if category != "system":
            metrics["category_availability"][category] = {
                "available": False,
                "reason": message,
                "confidence": "Unavailable",
            }
        self.logger.error(
            "Collector step failed: %s (%s: %s)",
            operation,
            type(exc).__name__,
            safe_path(str(exc)),
        )

    def mark_unavailable(self, metrics: dict[str, Any], category: str, reason: str) -> None:
        metrics.setdefault("category_availability", {})[category] = {
            "available": False,
            "reason": reason,
            "confidence": "Unavailable",
        }

    def set_confidence(self, metrics: dict[str, Any], category: str, confidence: str) -> None:
        state = metrics.setdefault("category_availability", {}).setdefault(category, {})
        state.update({"available": True, "reason": state.get("reason", ""), "confidence": confidence})

    def add_warning(
        self,
        metrics: dict[str, Any],
        category: str,
        operation: str,
        message: str,
        permission_related: bool = False,
    ) -> None:
        warning = CollectionWarning(category, operation, message, permission_related)
        metrics.setdefault("collection_warnings", []).append(warning.__dict__)

    def _finalize_availability(self, metrics: dict[str, Any]) -> None:
        required = {
            "memory": bool(metrics.get("ram_total_gb")),
            "storage": bool(metrics.get("sys_size_gb")),
            "diskspeed": bool(metrics.get("disk_type_known")),
            "cpu": bool(metrics.get("cpu_cores")),
            "gpu": bool(metrics.get("gpus")),
        }
        for category, present in required.items():
            state = metrics["category_availability"].setdefault(category, {
                "available": present,
                "reason": "" if present else "The operating system did not expose reliable data for this check.",
                "confidence": "Medium" if present else "Unavailable",
            })
            if not present and state.get("available", True):
                state.update({
                    "available": False,
                    "reason": "The operating system did not expose reliable data for this check.",
                    "confidence": "Unavailable",
                })

    def _safe(self, fn, default=None, operation: str = "optional check"):
        try:
            return fn()
        except Exception as exc:
            self.logger.debug("%s failed: %s", operation, type(exc).__name__)
            return default


__all__ = [
    "CategoryResult",
    "CollectionWarning",
    "Finding",
    "MetricCollector",
    "ScanResult",
    "Severity",
    "Upgrade",
]
