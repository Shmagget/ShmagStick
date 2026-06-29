"""CPU catalog with performance tiers (0-1000 scale)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CpuEntry:
    token: str
    name: str
    socket: str
    cores: int
    threads: int
    tdp: int
    rank: int
    search: str


_catalog: list[CpuEntry] = [
    CpuEntry("RYZEN 9 9950X3D", "AMD Ryzen 9 9950X3D", "AM5", 16, 32, 170, 990, "AMD Ryzen 9 9950X3D processor AM5"),
    CpuEntry("RYZEN 9 9950X", "AMD Ryzen 9 9950X", "AM5", 16, 32, 170, 970, "AMD Ryzen 9 9950X processor AM5"),
    CpuEntry("RYZEN 7 9800X3D", "AMD Ryzen 7 9800X3D", "AM5", 8, 16, 120, 960, "AMD Ryzen 7 9800X3D processor AM5"),
    CpuEntry("RYZEN 9 9900X", "AMD Ryzen 9 9900X", "AM5", 12, 24, 120, 930, "AMD Ryzen 9 9900X processor AM5"),
    CpuEntry("RYZEN 7 9700X", "AMD Ryzen 7 9700X", "AM5", 8, 16, 65, 875, "AMD Ryzen 7 9700X processor AM5"),
    CpuEntry("RYZEN 5 9600X", "AMD Ryzen 5 9600X", "AM5", 6, 12, 65, 830, "AMD Ryzen 5 9600X processor AM5"),
    CpuEntry("RYZEN 9 7950X3D", "AMD Ryzen 9 7950X3D", "AM5", 16, 32, 120, 950, "AMD Ryzen 9 7950X3D processor AM5"),
    CpuEntry("RYZEN 9 7950X", "AMD Ryzen 9 7950X", "AM5", 16, 32, 170, 940, "AMD Ryzen 9 7950X processor AM5"),
    CpuEntry("RYZEN 7 7800X3D", "AMD Ryzen 7 7800X3D", "AM5", 8, 16, 120, 920, "AMD Ryzen 7 7800X3D processor AM5"),
    CpuEntry("RYZEN 9 7900X", "AMD Ryzen 9 7900X", "AM5", 12, 24, 170, 900, "AMD Ryzen 9 7900X processor AM5"),
    CpuEntry("RYZEN 7 7700X", "AMD Ryzen 7 7700X", "AM5", 8, 16, 105, 825, "AMD Ryzen 7 7700X processor AM5"),
    CpuEntry("RYZEN 5 7600X", "AMD Ryzen 5 7600X", "AM5", 6, 12, 105, 780, "AMD Ryzen 5 7600X processor AM5"),
    CpuEntry("CORE ULTRA 9 285K", "Intel Core Ultra 9 285K", "LGA1851", 24, 24, 125, 950, "Intel Core Ultra 9 285K processor LGA1851"),
    CpuEntry("CORE ULTRA 7 265K", "Intel Core Ultra 7 265K", "LGA1851", 20, 20, 125, 900, "Intel Core Ultra 7 265K processor LGA1851"),
    CpuEntry("CORE ULTRA 5 245K", "Intel Core Ultra 5 245K", "LGA1851", 14, 14, 125, 820, "Intel Core Ultra 5 245K processor LGA1851"),
    CpuEntry("I9-14900K", "Intel Core i9-14900K", "LGA1700", 24, 32, 125, 940, "Intel Core i9-14900K processor LGA1700"),
    CpuEntry("I9-14900F", "Intel Core i9-14900F", "LGA1700", 24, 32, 65, 910, "Intel Core i9-14900F processor LGA1700"),
    CpuEntry("I7-14700K", "Intel Core i7-14700K", "LGA1700", 20, 28, 125, 895, "Intel Core i7-14700K processor LGA1700"),
    CpuEntry("I7-14700F", "Intel Core i7-14700F", "LGA1700", 20, 28, 65, 870, "Intel Core i7-14700F processor LGA1700"),
    CpuEntry("I5-14600K", "Intel Core i5-14600K", "LGA1700", 14, 20, 125, 800, "Intel Core i5-14600K processor LGA1700"),
    CpuEntry("I5-14400F", "Intel Core i5-14400F", "LGA1700", 10, 16, 65, 710, "Intel Core i5-14400F processor LGA1700"),
    CpuEntry("I9-13900K", "Intel Core i9-13900K", "LGA1700", 24, 32, 125, 920, "Intel Core i9-13900K processor LGA1700"),
    CpuEntry("I7-13700K", "Intel Core i7-13700K", "LGA1700", 16, 24, 125, 850, "Intel Core i7-13700K processor LGA1700"),
    CpuEntry("I5-13600K", "Intel Core i5-13600K", "LGA1700", 14, 20, 125, 780, "Intel Core i5-13600K processor LGA1700"),
    CpuEntry("I9-12900K", "Intel Core i9-12900K", "LGA1700", 16, 24, 125, 790, "Intel Core i9-12900K processor LGA1700"),
    CpuEntry("I7-12700K", "Intel Core i7-12700K", "LGA1700", 12, 20, 125, 720, "Intel Core i7-12700K processor LGA1700"),
    CpuEntry("I5-12600K", "Intel Core i5-12600K", "LGA1700", 10, 16, 125, 650, "Intel Core i5-12600K processor LGA1700"),
    CpuEntry("RYZEN 9 5950X", "AMD Ryzen 9 5950X", "AM4", 16, 32, 105, 790, "AMD Ryzen 9 5950X processor AM4"),
    CpuEntry("RYZEN 9 5900X", "AMD Ryzen 9 5900X", "AM4", 12, 24, 105, 740, "AMD Ryzen 9 5900X processor AM4"),
    CpuEntry("RYZEN 7 5800X3D", "AMD Ryzen 7 5800X3D", "AM4", 8, 16, 105, 735, "AMD Ryzen 7 5800X3D processor AM4"),
    CpuEntry("RYZEN 7 5800X", "AMD Ryzen 7 5800X", "AM4", 8, 16, 105, 670, "AMD Ryzen 7 5800X processor AM4"),
    CpuEntry("RYZEN 5 5600X", "AMD Ryzen 5 5600X", "AM4", 6, 12, 65, 560, "AMD Ryzen 5 5600X processor AM4"),
    CpuEntry("I9-10900K", "Intel Core i9-10900K", "LGA1200", 10, 20, 125, 635, "Intel Core i9-10900K BX8070110900K processor LGA1200"),
    CpuEntry("I9-10900KF", "Intel Core i9-10900KF", "LGA1200", 10, 20, 125, 632, "Intel Core i9-10900KF BX8070110900KF processor LGA1200"),
    CpuEntry("I9-10900", "Intel Core i9-10900", "LGA1200", 10, 20, 65, 610, "Intel Core i9-10900 BX8070110900 processor LGA1200"),
    CpuEntry("I9-10900F", "Intel Core i9-10900F", "LGA1200", 10, 20, 65, 608, "Intel Core i9-10900F BX8070110900F processor LGA1200"),
    CpuEntry("I9-10850K", "Intel Core i9-10850K", "LGA1200", 10, 20, 125, 615, "Intel Core i9-10850K BX8070110850K processor LGA1200"),
    CpuEntry("I7-10700K", "Intel Core i7-10700K", "LGA1200", 8, 16, 125, 560, "Intel Core i7-10700K BX8070110700K processor LGA1200"),
    CpuEntry("I7-10700KF", "Intel Core i7-10700KF", "LGA1200", 8, 16, 125, 558, "Intel Core i7-10700KF BX8070110700KF processor LGA1200"),
    CpuEntry("I7-10700", "Intel Core i7-10700", "LGA1200", 8, 16, 65, 535, "Intel Core i7-10700 BX8070110700 processor LGA1200"),
    CpuEntry("I7-10700F", "Intel Core i7-10700F", "LGA1200", 8, 16, 65, 533, "Intel Core i7-10700F BX8070110700F processor LGA1200"),
    CpuEntry("I5-10600K", "Intel Core i5-10600K", "LGA1200", 6, 12, 125, 465, "Intel Core i5-10600K BX8070110600K processor LGA1200"),
    CpuEntry("I5-10600KF", "Intel Core i5-10600KF", "LGA1200", 6, 12, 125, 463, "Intel Core i5-10600KF BX8070110600KF processor LGA1200"),
    CpuEntry("I5-10600", "Intel Core i5-10600", "LGA1200", 6, 12, 65, 440, "Intel Core i5-10600 BX8070110600 processor LGA1200"),
    CpuEntry("I5-10500", "Intel Core i5-10500", "LGA1200", 6, 12, 65, 415, "Intel Core i5-10500 BX8070110500 processor LGA1200"),
    CpuEntry("I5-10400F", "Intel Core i5-10400F", "LGA1200", 6, 12, 65, 395, "Intel Core i5-10400F BX8070110400F processor LGA1200"),
    CpuEntry("I5-10400", "Intel Core i5-10400", "LGA1200", 6, 12, 65, 393, "Intel Core i5-10400 BX8070110400 processor LGA1200"),
    CpuEntry("I3-10320", "Intel Core i3-10320", "LGA1200", 4, 8, 65, 340, "Intel Core i3-10320 BX8070110320 processor LGA1200"),
    CpuEntry("I3-10300", "Intel Core i3-10300", "LGA1200", 4, 8, 65, 315, "Intel Core i3-10300 BX8070110300 processor LGA1200"),
    CpuEntry("I3-10105F", "Intel Core i3-10105F", "LGA1200", 4, 8, 65, 305, "Intel Core i3-10105F BX8070110105F processor LGA1200"),
    CpuEntry("I3-10105", "Intel Core i3-10105", "LGA1200", 4, 8, 65, 305, "Intel Core i3-10105 BX8070110105 processor LGA1200"),
    CpuEntry("I3-10100F", "Intel Core i3-10100F", "LGA1200", 4, 8, 65, 295, "Intel Core i3-10100F BX8070110100F processor LGA1200"),
    CpuEntry("I3-10100", "Intel Core i3-10100", "LGA1200", 4, 8, 65, 295, "Intel Core i3-10100 BX8070110100 processor LGA1200"),
]

# Sort longest token first for greedy matching
CATALOG: list[CpuEntry] = sorted(_catalog, key=lambda e: len(e.token), reverse=True)


def find(token_or_name: str) -> CpuEntry | None:
    """Find a CPU by token or partial name match."""
    raw = token_or_name.upper()
    norm = _normalize(raw)
    for item in CATALOG:
        tok = item.token.upper()
        if raw == tok or tok in raw.upper() or norm in _normalize(tok):
            return item
    return None


def _normalize(value: str) -> str:
    import re
    v = value.upper()
    v = re.sub(r"\(R\)|\(TM\)|CPU|PROCESSOR|GRAPHICS|GEFORCE|RADEON|AMD|INTEL|NVIDIA|@.*$", " ", v)
    v = re.sub(r"[^A-Z0-9]+", " ", v)
    return v.strip()
