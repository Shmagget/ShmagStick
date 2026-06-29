"""GPU catalog with performance tiers (0-1000 scale)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GpuEntry:
    token: str
    name: str
    rank: int


_CATALOG: list[GpuEntry] = [
    GpuEntry("RTX 5090", "NVIDIA GeForce RTX 5090", 1000),
    GpuEntry("RTX 5080", "NVIDIA GeForce RTX 5080", 930),
    GpuEntry("RTX 5070 TI", "NVIDIA GeForce RTX 5070 Ti", 855),
    GpuEntry("RTX 5070", "NVIDIA GeForce RTX 5070", 800),
    GpuEntry("RTX 4090", "NVIDIA GeForce RTX 4090", 950),
    GpuEntry("RTX 4080 SUPER", "NVIDIA GeForce RTX 4080 SUPER", 850),
    GpuEntry("RTX 4080", "NVIDIA GeForce RTX 4080", 830),
    GpuEntry("RTX 4070 TI SUPER", "NVIDIA GeForce RTX 4070 Ti SUPER", 780),
    GpuEntry("RTX 4070 TI", "NVIDIA GeForce RTX 4070 Ti", 745),
    GpuEntry("RTX 4070 SUPER", "NVIDIA GeForce RTX 4070 SUPER", 710),
    GpuEntry("RTX 4070", "NVIDIA GeForce RTX 4070", 665),
    GpuEntry("RTX 4060 TI", "NVIDIA GeForce RTX 4060 Ti", 560),
    GpuEntry("RTX 4060", "NVIDIA GeForce RTX 4060", 480),
    GpuEntry("RTX 3090 TI", "NVIDIA GeForce RTX 3090 Ti", 735),
    GpuEntry("RTX 3090", "NVIDIA GeForce RTX 3090", 705),
    GpuEntry("RTX 3080 TI", "NVIDIA GeForce RTX 3080 Ti", 685),
    GpuEntry("RTX 3080", "NVIDIA GeForce RTX 3080", 640),
    GpuEntry("RTX 3070 TI", "NVIDIA GeForce RTX 3070 Ti", 560),
    GpuEntry("RTX 3070", "NVIDIA GeForce RTX 3070", 520),
    GpuEntry("RTX 3060 TI", "NVIDIA GeForce RTX 3060 Ti", 475),
    GpuEntry("RTX 3060", "NVIDIA GeForce RTX 3060", 390),
    GpuEntry("RX 7900 XTX", "AMD Radeon RX 7900 XTX", 810),
    GpuEntry("RX 7900 XT", "AMD Radeon RX 7900 XT", 745),
    GpuEntry("RX 7900 GRE", "AMD Radeon RX 7900 GRE", 660),
    GpuEntry("RX 7800 XT", "AMD Radeon RX 7800 XT", 610),
    GpuEntry("RX 7700 XT", "AMD Radeon RX 7700 XT", 535),
    GpuEntry("RX 7600 XT", "AMD Radeon RX 7600 XT", 430),
    GpuEntry("RX 7600", "AMD Radeon RX 7600", 390),
    GpuEntry("RX 6950 XT", "AMD Radeon RX 6950 XT", 670),
    GpuEntry("RX 6900 XT", "AMD Radeon RX 6900 XT", 635),
    GpuEntry("RX 6800 XT", "AMD Radeon RX 6800 XT", 585),
    GpuEntry("RX 6800", "AMD Radeon RX 6800", 535),
    GpuEntry("RX 6700 XT", "AMD Radeon RX 6700 XT", 450),
    GpuEntry("RX 6600 XT", "AMD Radeon RX 6600 XT", 335),
    GpuEntry("RX 6600", "AMD Radeon RX 6600", 300),
    GpuEntry("ARC B580", "Intel Arc B580", 455),
    GpuEntry("ARC B570", "Intel Arc B570", 410),
    GpuEntry("ARC A770", "Intel Arc A770", 370),
    GpuEntry("ARC A750", "Intel Arc A750", 340),
    GpuEntry("GTX 1660 SUPER", "NVIDIA GeForce GTX 1660 SUPER", 265),
]

CATALOG: list[GpuEntry] = sorted(_CATALOG, key=lambda e: len(e.token), reverse=True)


def find(name: str) -> GpuEntry | None:
    norm = _normalize(name)
    for item in CATALOG:
        if norm in _normalize(item.name) or norm in _normalize(item.token):
            return item
    return None


def _normalize(value: str) -> str:
    import re
    v = value.upper()
    v = re.sub(r"\(R\)|\(TM\)|CPU|PROCESSOR|GRAPHICS|GEFORCE|RADEON|AMD|INTEL|NVIDIA|@.*$", " ", v)
    v = re.sub(r"[^A-Z0-9]+", " ", v)
    return v.strip()
