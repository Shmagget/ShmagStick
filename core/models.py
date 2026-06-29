"""Typed models shared by collection, scoring, the GUI, and reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


class Confidence(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    UNAVAILABLE = "Unavailable"


class CategoryStatus(str, Enum):
    HEALTHY = "Healthy"
    ATTENTION = "Needs attention"
    CRITICAL = "Critical"
    UNAVAILABLE = "Unavailable"


@dataclass
class CollectionWarning:
    category: str
    operation: str
    message: str
    permission_related: bool = False


@dataclass
class Finding:
    severity: str
    title: str
    detail: str
    action: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class Upgrade:
    kind: str
    text: str
    url: str = ""
    note: str = ""
    upgrade_type: str = ""
    why: str = ""
    current_part: str = "Unavailable"
    minimum_target: str = ""
    better_target: str = ""
    compatibility_confidence: str = Confidence.LOW.value
    verify_before_buying: list[str] = field(default_factory=list)
    priority: str = "Low"
    diy_friendly: str = "Varies"


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
    status: str = ""
    grade: str = ""
    reason: str = ""
    evidence: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    confidence: str = Confidence.MEDIUM.value
    unavailable_reason: str = ""
    scored: bool = True

    def finalize(self) -> "CategoryResult":
        if not self.scored or self.unavailable_reason:
            self.scored = False
            self.status = CategoryStatus.UNAVAILABLE.value
            self.grade = "N/A"
            self.reason = self.unavailable_reason or "This check could not be completed."
            self.confidence = Confidence.UNAVAILABLE.value
            self.evidence = self.evidence or [self.stat]
            return self

        self.score = max(0, min(100, int(round(self.score))))
        if self.confidence == Confidence.LOW.value:
            self.score = min(self.score, 80)
        self.grade = grade_for_score(self.score)
        severities = {finding.severity for finding in self.findings}
        if Severity.CRITICAL.value in severities or self.score < 40:
            self.status = CategoryStatus.CRITICAL.value
        elif (self.score < 80 or self.confidence == Confidence.LOW.value
              or severities.intersection({Severity.HIGH.value, Severity.MEDIUM.value})):
            self.status = CategoryStatus.ATTENTION.value
        else:
            self.status = CategoryStatus.HEALTHY.value

        non_info = [finding for finding in self.findings if finding.severity != Severity.INFO.value]
        if non_info:
            self.reason = non_info[0].title
        elif self.confidence == Confidence.LOW.value and self.findings:
            self.reason = self.findings[0].title
        else:
            self.reason = "No significant issue was detected."
        if not self.evidence:
            self.evidence = [self.stat]
            self.evidence.extend(finding.detail for finding in self.findings if finding.detail)
        if not self.recommendations:
            self.recommendations = list(dict.fromkeys(
                finding.action for finding in self.findings if finding.action
            ))
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    profile: str
    blurb: str
    overall: int
    grade: str
    grade_label: str
    categories: list[CategoryResult] = field(default_factory=list)
    prioritized_actions: list[dict[str, str]] = field(default_factory=list)
    upgrades: list[Upgrade] = field(default_factory=list)
    unavailable_checks: list[str] = field(default_factory=list)


def grade_for_score(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 55:
        return "D"
    return "F"
