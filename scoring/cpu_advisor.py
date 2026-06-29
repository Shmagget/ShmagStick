"""CPU upgrade advisor — ports Get-CpuUpgradeAdvice logic."""

from __future__ import annotations

import re

from catalogs.cpus import find as find_cpu, CATALOG as CPU_CATALOG
from catalogs.boards import find as find_board


_SOCKET_RE = re.compile(
    r"(AM4|AM5|LGA\s*\d+|sTRX4|sWRX8|TR4)", re.IGNORECASE
)
_INTEL_GEN_RE = re.compile(r"Core\(TM\)\s+i[3579]-([0-9]{4,5})", re.IGNORECASE)
_INTEL_ULTRA_RE = re.compile(r"Intel\(R\)\s+Core\(TM\)\s+Ultra\s+([0-9])", re.IGNORECASE)
_RYZEN_RE = re.compile(r"Ryzen\s+[3579]\s+([0-9]{4})", re.IGNORECASE)
_MOBILE_RE = re.compile(
    r"\bi[3-9]-\d{3,5}(HX|HK|H|U|P|Y|G[0-9])\b"
    r"|\bUltra\s+\d\s+\d{3}(HX|H|U|V|P)\b"
    r"|\bRyzen\s+\d\s+\d{3,4}(HX|HS|H|U|C)\b",
    re.IGNORECASE,
)


def cpu_model_token(cpu_name: str) -> str:
    n = cpu_name.upper()
    m = re.search(r"(I[3579]-[0-9]{4,5}[A-Z]{0,2})", n)
    if m:
        return m.group(1)
    m = re.search(r"(CORE\s+ULTRA\s+[579]\s+[0-9]{3}K?)", n)
    if m:
        return re.sub(r"\s+", " ", m.group(1))
    m = re.search(r"(RYZEN\s+[3579]\s+[0-9]{4}X3D)", n)
    if m:
        return re.sub(r"\s+", " ", m.group(1))
    m = re.search(r"(RYZEN\s+[3579]\s+[0-9]{4}X?)", n)
    if m:
        return re.sub(r"\s+", " ", m.group(1))
    return ""


def infer_socket(cpu_name: str) -> tuple[str, str]:
    """Return (socket, confidence)."""
    n = cpu_name
    m = _SOCKET_RE.search(n)
    if m:
        return m.group(1).upper().replace(" ", ""), "detected"

    if re.search("AMD|Ryzen", n, re.IGNORECASE):
        s = _RYZEN_RE.search(n)
        if s:
            series = int(s.group(1))
            if series >= 7000:
                return "AM5", "inferred from Ryzen series"
            elif series >= 1000:
                return "AM4", "inferred from Ryzen series"
        if re.search("Threadripper", n, re.IGNORECASE):
            s = _RYZEN_RE.search(n)
            if s and int(s.group(1)) >= 3000:
                return "sTRX4", "inferred from CPU family"
            return "TR4", "inferred from CPU family"

    if re.search("Intel", n, re.IGNORECASE):
        m2 = _INTEL_GEN_RE.search(n)
        if m2:
            gen = int(m2.group(1)[:2])
        else:
            m2 = _INTEL_ULTRA_RE.search(n)
            if m2:
                gen = 15
            else:
                gen = 0
        if gen >= 15:
            return "LGA1851", "inferred from Intel generation"
        elif gen >= 12:
            return "LGA1700", "inferred from Intel generation"
        elif gen >= 10:
            return "LGA1200", "inferred from Intel generation"
        elif gen >= 8:
            return "LGA1151-8TH", "inferred from Intel generation"
        elif gen >= 6:
            return "LGA1151-6TH", "inferred from Intel generation"

    return "", "low"


def is_mobile(cpu_name: str) -> bool:
    return bool(_MOBILE_RE.search(cpu_name))


def _preferred_from_tokens(tokens: list[str], current_rank: int):
    for tok in tokens:
        item = find_cpu(tok)
        if item and item.rank > current_rank:
            return item
    for tok in tokens:
        item = find_cpu(tok)
        if item:
            return item
    return None


def _generic_rec(socket: str, has_dedicated_gpu: bool):
    s = socket.upper()
    table = {
        "LGA1851": ["CORE ULTRA 9 285K", "CORE ULTRA 7 265K"],
        "LGA1700": ["I7-14700F", "I7-14700K", "I9-14900F", "I9-14900K"],
        "LGA1200": (
            ["I9-10900F", "I9-10900", "I7-10700F", "I7-10700"]
            if has_dedicated_gpu
            else ["I9-10900", "I7-10700", "I5-10600"]
        ),
        "AM5": ["RYZEN 7 9800X3D", "RYZEN 9 9950X", "RYZEN 9 9900X", "RYZEN 7 9700X"],
        "AM4": ["RYZEN 7 5800X3D", "RYZEN 9 5900X", "RYZEN 9 5950X", "RYZEN 7 5800X"],
    }
    tokens = table.get(s, [])
    return _preferred_from_tokens(tokens, 0)


def advise(cpu_name: str, board_name: str, socket: str,
           has_dedicated_gpu: bool, is_laptop: bool) -> dict:
    if is_mobile(cpu_name) or is_laptop:
        return {
            "can_buy": False,
            "text": "This CPU is soldered (laptop/mobile) - a CPU swap is not practical",
            "query": "",
            "note": "Mobile/laptop CPUs are soldered to the board and cannot be replaced. RAM, SSD, cooling service, and power settings are the realistic upgrades here.",
            "confidence": "laptop detected" if is_laptop else "mobile/soldered CPU detected",
            "recommended": "",
            "rank": 0,
            "support_url": "",
        }

    token = cpu_model_token(cpu_name)
    current = find_cpu(token) if token else find_cpu(cpu_name)
    current_rank = current.rank if current else 0
    board_profile = find_board(board_name) if board_name else None

    if board_profile:
        tokens = (
            board_profile.preferred_with_gpu
            if has_dedicated_gpu
            else board_profile.preferred_without_gpu
        )
        rec = _preferred_from_tokens(tokens, current_rank)
        if rec:
            delta = f" Upgrade tier: {rec.rank} vs current tier {current_rank}." if current_rank else ""
            note = (
                f"Known board profile: {board_profile.match}. {board_profile.board_note} "
                f"Current CPU: {current.name if current else cpu_name}.{delta} "
                f"Confirm BIOS support before buying: {board_profile.support_url}"
            )
            return {
                "can_buy": True,
                "text": f"Recommended CPU upgrade: {rec.name}",
                "query": rec.search,
                "note": note,
                "confidence": "board compatibility table",
                "recommended": rec.name,
                "rank": rec.rank,
                "support_url": board_profile.support_url,
            }

    inferred_socket, confidence = socket, "detected"
    if not inferred_socket:
        inferred_socket, confidence = infer_socket(cpu_name)

    if inferred_socket:
        return {
            "can_buy": False,
            "text": f"A {inferred_socket} CPU upgrade may be possible, but compatibility is not confirmed",
            "query": "",
            "note": (
                f"Detected board: {board_name or 'unknown'}. Socket/platform was {confidence}, "
                "but socket alone is insufficient. Check the exact motherboard support list and BIOS version before selecting a CPU."
            ),
            "confidence": confidence,
            "recommended": "",
            "rank": 0,
            "support_url": "",
        }

    if board_name:
        return {
            "can_buy": False,
            "text": "CPU compatibility requires the motherboard vendor support list",
            "query": "",
            "note": (
                f"Windows did not expose a reliable socket, so this uses the motherboard model: {board_name}. "
                f"Confirm the vendor CPU support list before buying."
            ),
            "confidence": "motherboard model only",
            "recommended": "",
            "rank": 0,
            "support_url": "",
        }

    return {
        "can_buy": False,
        "text": "CPU upgrade compatibility could not be determined",
        "query": "",
        "note": (
            "Windows did not expose the motherboard/socket. Use the current CPU as a starting point "
            "and confirm board/socket/BIOS support before buying."
        ),
        "confidence": "low",
        "recommended": "",
        "rank": 0,
        "support_url": "",
    }
