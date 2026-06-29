"""Abstract base class for platform-specific metric collectors."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


@dataclass
class Finding:
    severity: str
    title: str
    detail: str
    action: str


@dataclass
class Upgrade:
    kind: str  # "buy" | "free" | "ok" | "advisory"
    text: str
    url: str = ""
    note: str = ""


@dataclass
class CategoryResult:
    key: str
    name: str
    icon: str
    score: int
    weight: int
    stat: str
    findings: list[Finding] = field(default_factory=list)
    upgrade: Upgrade | None = None


@dataclass
class ScanResult:
    profile: str
    blurb: str
    overall: int
    grade: str
    grade_label: str
    categories: list[CategoryResult] = field(default_factory=list)


class MetricCollector(abc.ABC):
    """Abstract base class — each platform implements all 13 collect methods."""

    @abc.abstractmethod
    def collect(self) -> dict[str, Any]:
        """Run all metric collection and return a flat dict of all measurements."""
        ...

    # -- helpers available to all subclasses --

    def _safe(self, fn, default=None):
        """Run fn, return default on any exception."""
        try:
            return fn()
        except Exception:
            return default


