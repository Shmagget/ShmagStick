"""Extensive, read-only "deep scan".

This goes beyond the standard health checks to help answer two questions:

  * "What is taking up all my space / slowing my disk down?"  -> largest files
    and folders in the areas a user actually fills up.
  * "Do I have anything malicious or suspicious?"  -> programs running from
    risky locations, suspicious files, and — on Windows — the threat history
    that Windows Security (Defender) has *already* recorded.

IMPORTANT: this is a heuristic helper, NOT antivirus. It never opens file
contents, matches virus signatures, quarantines, or deletes anything. It only
reads metadata and surfaces what the operating system's own security already
found. Findings labelled "suspicious" are prompts to review, not verdicts.
"""

from __future__ import annotations

import heapq
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import psutil

WINDOWS = sys.platform == "win32"
_NO_WINDOW = 0x08000000 if WINDOWS else 0  # CREATE_NO_WINDOW

# Heuristic: software launched from a temp or downloads folder is an unusual
# (not certain) malware pattern. We deliberately exclude AppData\Roaming and
# AppData\Local\Programs because countless legitimate apps (Discord, Slack,
# Spotify, etc.) run from there — flagging them would just be noise.
_RISKY_MARKERS = (
    ("\\appdata\\local\\temp\\", "\\windows\\temp\\", "\\temp\\", "\\downloads\\")
    if WINDOWS
    else ("/tmp/", "/var/tmp/", "/downloads/")
)

_EXEC_SUFFIXES = (
    {".exe", ".scr", ".com", ".pif", ".bat", ".cmd", ".vbs", ".js", ".jse", ".wsf", ".ps1", ".msi"}
    if WINDOWS
    else {".sh", ".run", ".bin", ".appimage"}
)
_DOC_THEN_EXEC = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".jpg", ".jpeg", ".png", ".zip", ".rar", ".csv")


def _emit(progress, pct: int, label: str) -> None:
    if progress:
        progress(pct, label)


def collect_deep(metrics: dict, progress=None) -> dict:
    """Populate ``metrics['deep']`` with deep-scan findings. Always read-only."""
    deep: dict = {}
    metrics["deep"] = deep
    _emit(progress, 2, "Deep scan: locating large files")

    large, big_dirs, scanned, capped = _scan_large_files(progress)
    deep["large_files"] = large
    deep["big_dirs"] = big_dirs
    deep["files_scanned"] = scanned
    deep["scan_capped"] = capped

    _emit(progress, 64, "Deep scan: inspecting running programs")
    deep["suspicious_processes"] = _suspicious_processes()

    _emit(progress, 76, "Deep scan: checking risky file locations")
    deep["suspicious_files"] = _suspicious_files()

    if WINDOWS:
        _emit(progress, 86, "Deep scan: reading Windows Security history")
        deep["defender"] = _defender_status_and_threats()
    else:
        deep["defender"] = {"available": False}

    _emit(progress, 100, "Deep scan complete")
    return deep


# ---------------------------------------------------------------------------
# Large files / space hogs
# ---------------------------------------------------------------------------

def _scan_roots() -> list[Path]:
    home = Path.home()
    candidates = [home / name for name in
                  ("Downloads", "Desktop", "Documents", "Videos", "Pictures", "Music")]
    if WINDOWS:
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local))
    else:
        candidates.append(home / ".cache")

    roots, seen = [], set()
    for path in candidates:
        try:
            if path.is_dir():
                key = str(path.resolve()).lower()
                if key not in seen:
                    seen.add(key)
                    roots.append(path)
        except OSError:
            continue
    return roots


def _scan_large_files(progress=None, top_n: int = 15, max_files: int = 300_000,
                      time_budget: float = 30.0):
    """Find the largest individual files without reading any file contents.

    Bounded by a file count and a wall-clock budget so it can never hang on a
    huge tree. Symlinks/reparse points are skipped.
    """
    roots = _scan_roots()
    heap: list[tuple[int, str]] = []  # min-heap of (size, path)
    dir_totals: dict[str, int] = {}
    scanned = 0
    capped = False
    start = time.time()

    for index, root in enumerate(roots):
        _emit(progress, 2 + int((index / max(1, len(roots))) * 58),
              f"Deep scan: scanning {root.name or root}")
        root_key = str(root)
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            if scanned > max_files or (time.time() - start) > time_budget:
                capped = True
                break
            for filename in filenames:
                scanned += 1
                full = os.path.join(dirpath, filename)
                try:
                    info = os.lstat(full)
                    if not stat.S_ISREG(info.st_mode):
                        continue
                    size = info.st_size
                except OSError:
                    continue
                dir_totals[root_key] = dir_totals.get(root_key, 0) + size
                if len(heap) < top_n:
                    heapq.heappush(heap, (size, full))
                elif size > heap[0][0]:
                    heapq.heapreplace(heap, (size, full))
        if capped:
            break

    large = [{"path": path, "size": size}
             for size, path in sorted(heap, key=lambda item: item[0], reverse=True)]
    big_dirs = [{"path": path, "size": size}
                for path, size in sorted(dir_totals.items(), key=lambda item: item[1], reverse=True)]
    return large, big_dirs, scanned, capped


# ---------------------------------------------------------------------------
# Suspicious processes / files
# ---------------------------------------------------------------------------

def _suspicious_processes() -> list[dict]:
    found: dict[str, dict] = {}
    for proc in psutil.process_iter(["name", "exe"]):
        try:
            exe = proc.info.get("exe") or ""
            if not exe:
                continue
            low = exe.replace("/", "\\").lower() if WINDOWS else exe.lower()
            marker = next((m for m in _RISKY_MARKERS if m in low), None)
            if marker and exe not in found:
                found[exe] = {
                    "name": proc.info.get("name") or os.path.basename(exe),
                    "exe": exe,
                    "location": marker.strip("\\/"),
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    flagged = list(found.values())
    if WINDOWS:
        # Signature check is relatively slow, so only for the (few) flagged ones.
        for item in flagged[:8]:
            item["signed"] = _authenticode(item["exe"])
    return flagged[:15]


def _suspicious_files() -> list[dict]:
    home = Path.home()
    scan_dirs = [home / "Downloads", home / "Desktop"]
    if WINDOWS:
        for env in ("TEMP", "TMP"):
            value = os.environ.get(env)
            if value:
                scan_dirs.append(Path(value))

    results: list[dict] = []
    seen: set[str] = set()
    sig_checks = 0          # each signature check spawns PowerShell, so bound them
    max_sig_checks = 12
    for directory in scan_dirs:
        try:
            if not directory.is_dir():
                continue
            for entry in os.scandir(directory):
                if len(results) >= 25:
                    break
                try:
                    if not entry.is_file(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                name = entry.name
                low = name.lower()
                suffix = os.path.splitext(low)[1]
                if suffix not in _EXEC_SUFFIXES:
                    continue
                if entry.path in seen:
                    continue

                reasons = []
                stem = os.path.splitext(low)[0]
                if any(stem.endswith(doc) for doc in _DOC_THEN_EXEC):
                    reasons.append("file pretends to be a document but is actually executable (double extension)")
                if WINDOWS and suffix in {".vbs", ".js", ".jse", ".bat", ".cmd", ".ps1", ".wsf", ".scr"}:
                    reasons.append(f"script/executable ({suffix}) sitting in {directory.name}")
                if WINDOWS and suffix in {".exe", ".msi", ".scr"} and sig_checks < max_sig_checks:
                    sig_checks += 1
                    sig = _authenticode(entry.path)
                    if sig in ("NotSigned", "HashMismatch", "NotTrusted"):
                        reasons.append(f"unsigned executable ({sig})")

                if reasons:
                    seen.add(entry.path)
                    results.append({
                        "name": name,
                        "severity": "High" if len(reasons) > 1 else "Medium",
                        "detail": f"Location: {entry.path}. Why flagged: {'; '.join(reasons)}.",
                    })
        except OSError:
            continue
    return results


def _authenticode(path: str) -> str:
    """Return the Authenticode signature status of a file, or '' if unknown."""
    if not WINDOWS:
        return ""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "& { param($p) (Get-AuthenticodeSignature -LiteralPath $p).Status.ToString() }", path],
            capture_output=True, text=True, timeout=8, creationflags=_NO_WINDOW,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


# ---------------------------------------------------------------------------
# Windows Security (Defender) — surface what the OS already found
# ---------------------------------------------------------------------------

_DEFENDER_PS = r"""
$ErrorActionPreference = "SilentlyContinue"
$st = Get-MpComputerStatus
$names = @{}
foreach ($t in (Get-MpThreat)) { if ($t.ThreatName) { $names[[string]$t.ThreatID] = $t.ThreatName } }
$list = @()
foreach ($d in (Get-MpThreatDetection | Sort-Object InitialDetectionTime -Descending | Select-Object -First 20)) {
  $list += [pscustomobject]@{
    time     = ($d.InitialDetectionTime | Out-String).Trim()
    name     = $names[[string]$d.ThreatID]
    threatId = [string]$d.ThreatID
    files    = (@($d.Resources) -join " | ")
    cleaned  = [bool]$d.ActionSuccess
  }
}
[pscustomobject]@{
  rtp        = $st.RealTimeProtectionEnabled
  av         = $st.AntivirusEnabled
  quick      = ($st.QuickScanEndTime | Out-String).Trim()
  full       = ($st.FullScanEndTime | Out-String).Trim()
  sigAge     = $st.AntivirusSignatureAge
  detections = @($list)
} | ConvertTo-Json -Depth 4 -Compress
"""


def _defender_status_and_threats() -> dict:
    info = {"available": False, "rtp": None, "av_enabled": None,
            "quick": None, "full": None, "sig_age": None, "detections": []}
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _DEFENDER_PS],
            capture_output=True, text=True, timeout=40, creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return info
    if result.returncode != 0 or not result.stdout.strip():
        return info
    try:
        data = json.loads(result.stdout)
    except (ValueError, json.JSONDecodeError):
        return info
    if not isinstance(data, dict):
        return info

    detections = data.get("detections") or []
    if isinstance(detections, dict):
        detections = [detections]
    info.update({
        "available": True,
        "rtp": data.get("rtp"),
        "av_enabled": data.get("av"),
        "quick": data.get("quick") or None,
        "full": data.get("full") or None,
        "sig_age": data.get("sigAge"),
        "detections": detections,
    })
    return info
