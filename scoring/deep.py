"""Turn raw deep-scan data (metrics['deep']) into displayable sections.

These sections render with the same collapsible widget as the scored categories
but carry weight 0 — they are informational and never change the overall grade.
"""

from __future__ import annotations

import sys

from core.models import CategoryResult, Finding

WINDOWS = sys.platform == "win32"

_GB = 1024 ** 3
_MB = 1024 ** 2


def _human(num: float) -> str:
    size = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def build_deep_sections(metrics: dict) -> list[CategoryResult]:
    deep = metrics.get("deep")
    if not deep:
        return []
    sections = [_space_section(deep), _threats_section(deep)]
    return [section for section in sections if section is not None]


# ---------------------------------------------------------------------------

def _space_section(deep: dict) -> CategoryResult:
    large = deep.get("large_files", [])
    big_dirs = deep.get("big_dirs", [])
    scanned = deep.get("files_scanned", 0)
    capped = deep.get("scan_capped", False)
    biggest = large[0]["size"] if large else 0

    findings: list[Finding] = []
    if large:
        listing = "\n".join(f"{_human(item['size'])}   {item['path']}" for item in large[:12])
        findings.append(Finding(
            severity="Low" if biggest >= 2 * _GB else "Info",
            title=f"{len(large)} largest files found",
            detail=listing,
            action="Review these and delete or move any you no longer need. ShmagStick never deletes anything for you.",
        ))
    if big_dirs:
        listing = "\n".join(f"{_human(item['size'])}   {item['path']}" for item in big_dirs[:8])
        findings.append(Finding(
            severity="Info",
            title="Folders holding the most data (of the areas scanned)",
            detail=listing,
            action="",
        ))
    if capped:
        findings.append(Finding(
            severity="Info",
            title="Scan was limited for speed",
            detail=f"Stopped after about {scanned:,} files or the time budget was reached. "
                   "Common user folders and the local app-data cache were prioritised.",
            action="",
        ))
    if not findings:
        findings.append(Finding("Info", "No large files were found in the scanned areas", "", ""))

    score = 75 if biggest >= 5 * _GB else (82 if biggest >= 1 * _GB else 92)
    cat = CategoryResult(
        key="deep_space",
        name="Disk Space Hogs (Deep Scan)",
        icon="\U0001F9F9",  # broom
        score=score,
        weight=0,
        stat=f"{scanned:,} files scanned" + (" · limited for speed" if capped else ""),
        findings=findings,
        confidence="High",
    )
    cat.finalize()
    return cat


def _threats_section(deep: dict) -> CategoryResult:
    defender = deep.get("defender") or {}
    processes = deep.get("suspicious_processes", [])
    files = deep.get("suspicious_files", [])
    detections = defender.get("detections", []) if defender.get("available") else []
    uncleaned = [d for d in detections if not d.get("cleaned")]

    findings: list[Finding] = []

    for detection in detections[:8]:
        name = detection.get("name") or f"Threat ID {detection.get('threatId', '?')}"
        cleaned = detection.get("cleaned")
        findings.append(Finding(
            severity="Critical" if not cleaned else "High",
            title=f"Windows Security detected: {name}",
            detail=f"When: {detection.get('time', '?')}   ·   "
                   f"File(s): {detection.get('files') or 'n/a'}   ·   "
                   f"Remediated: {'yes' if cleaned else 'NO — may still need action'}",
            action=("Already handled by Windows Security; usually no action needed."
                    if cleaned else
                    "Open Windows Security → Protection history and follow its recommended action."),
        ))

    for proc in processes[:10]:
        signed = proc.get("signed")
        unsigned = signed not in (None, "", "Valid")
        sig_note = f" Signature status: {signed}." if signed else ""
        findings.append(Finding(
            severity="High" if unsigned else "Medium",
            title=f"Program running from a risky location: {proc['name']}",
            detail=f"Path: {proc['exe']}.{sig_note} Software running from Temp/Downloads/AppData is a "
                   "common malware pattern — though many legitimate installers and updaters do this too.",
            action="If you don't recognise it, search the name before trusting it and run a full Windows Security scan.",
        ))

    for item in files[:10]:
        findings.append(Finding(
            severity=item.get("severity", "Medium"),
            title=f"Suspicious file: {item['name']}",
            detail=item.get("detail", ""),
            action="Don't open it unless you trust where it came from; right-click it and scan with your security software.",
        ))

    if defender.get("available"):
        rtp = defender.get("rtp")
        rtp_text = "on" if rtp else ("off" if rtp is False else "unknown")
        sig_age = defender.get("sig_age")
        sig_text = f"{sig_age} day(s)" if sig_age is not None else "unknown"
        findings.append(Finding(
            severity="Info",
            title="Windows Security status",
            detail=f"Real-time protection: {rtp_text}   ·   Last quick scan: {defender.get('quick') or 'unknown'}   ·   "
                   f"Last full scan: {defender.get('full') or 'unknown'}   ·   Signature age: {sig_text}",
            action="",
        ))
    elif WINDOWS:
        findings.append(Finding(
            severity="Info",
            title="Windows Security history was unavailable",
            detail="Could not read Defender status/history. A third-party antivirus may be in charge, or permission was denied.",
            action="Check your antivirus product directly.",
        ))

    findings.append(Finding(
        severity="Info",
        title="About this check — please read",
        detail="This deep scan is a read-only helper, not antivirus. It surfaces what your operating system's "
               "security already found plus heuristic indicators. It does not open file contents, match virus "
               "signatures, quarantine, or remove anything. Treat 'suspicious' items as prompts to review.",
        action="",
    ))

    has_unsigned_proc = any(p.get("signed") not in (None, "", "Valid") for p in processes)
    if uncleaned or has_unsigned_proc:
        score = 22
    elif detections or processes or files:
        score = 50
    else:
        score = 92

    cat = CategoryResult(
        key="deep_threats",
        name="Threats & Suspicious Items (Deep Scan)",
        icon="\U0001F9A0",  # microbe
        score=score,
        weight=0,
        stat=f"{len(detections)} past detection(s) · {len(processes)} risky program(s) · {len(files)} suspicious file(s)",
        findings=findings,
        confidence="Medium" if defender.get("available") or not WINDOWS else "Low",
    )
    cat.finalize()
    return cat
