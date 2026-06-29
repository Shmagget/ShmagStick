"""Motherboard compatibility table for CPU upgrade advice."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoardEntry:
    match: str          # substring match against detected board name
    socket: str         # e.g. AM5, LGA1700
    support_url: str    # vendor CPU support list URL
    board_note: str     # human-readable context
    preferred_with_gpu: list[str]   # CPU tokens to prefer when dGPU present
    preferred_without_gpu: list[str]
    compatible: list[str]           # all compatible CPU tokens


_catalog: list[BoardEntry] = [
    BoardEntry(
        match="ASRock B460 Phantom Gaming 4",
        socket="LGA1200",
        support_url="https://www.asrock.com/support/cpu.asp?s=1200&u=1196",
        board_note="ASRock lists this Intel B460 board as Socket 1200 with support for 10th Gen Intel Core processors.",
        preferred_with_gpu=["I9-10900F","I9-10900","I7-10700F","I7-10700","I5-10600"],
        preferred_without_gpu=["I9-10900","I7-10700","I5-10600","I5-10500","I5-10400"],
        compatible=["I9-10900K","I9-10900KF","I9-10900","I9-10900F","I9-10850K","I7-10700K","I7-10700KF","I7-10700","I7-10700F","I5-10600K","I5-10600KF","I5-10600","I5-10500","I5-10400F","I5-10400","I3-10320","I3-10300","I3-10105F","I3-10105","I3-10100F","I3-10100"],
    ),
    BoardEntry(
        match="ASRock Z490 Taichi",
        socket="LGA1200",
        support_url="https://www.asrock.com/support/cpu.asp?s=1200&u=1196",
        board_note="Z490 chipset, supports 10th and 11th Gen Intel Core.",
        preferred_with_gpu=["I9-10900K","I9-10850K","I7-10700K","I7-11700K"],
        preferred_without_gpu=["I9-10900K","I9-10900","I7-10700K","I7-10700","I5-10600K"],
        compatible=["I9-10900K","I9-10900KF","I9-10900","I9-10900F","I9-10850K","I7-10700K","I7-10700KF","I7-10700","I7-10700F","I5-10600K","I5-10600KF","I5-10600","I5-10500","I5-10400F","I5-10400","I3-10320","I3-10300","I3-10105F","I3-10105","I3-10100F","I3-10100"],
    ),
    # --- AM5 ---
    BoardEntry(
        match="ASUS ROG Crosshair X670E Hero",
        socket="AM5",
        support_url="https://rog.asus.com/motherboards/rog-crosshair/rog-crosshair-x670e-hero-model/helpdesk_download/",
        board_note="X670E chipset, supports Ryzen 7000/8000/9000 series. Dual PCIe 5.0 M.2 + GPU.",
        preferred_with_gpu=["RYZEN 9 9950X","RYZEN 9 9900X","RYZEN 7 9800X3D","RYZEN 9 7950X"],
        preferred_without_gpu=["RYZEN 9 7950X","RYZEN 9 7950X3D","RYZEN 7 7800X3D"],
        compatible=["RYZEN 9 9950X3D","RYZEN 9 9950X","RYZEN 9 9900X","RYZEN 7 9800X3D","RYZEN 7 9700X","RYZEN 5 9600X","RYZEN 9 7950X3D","RYZEN 9 7950X","RYZEN 7 7800X3D","RYZEN 9 7900X","RYZEN 7 7700X","RYZEN 5 7600X"],
    ),
    BoardEntry(
        match="MSI MAG B650 Tomahawk WiFi",
        socket="AM5",
        support_url="https://www.msi.com/Motherboard/MAG-B650-TOMAHAWK-WIFI/support#cpu",
        board_note="B650 chipset, DDR5, PCIe 4.0. Supports Ryzen 7000/8000/9000.",
        preferred_with_gpu=["RYZEN 9 9900X","RYZEN 7 9800X3D","RYZEN 9 7950X"],
        preferred_without_gpu=["RYZEN 9 7950X","RYZEN 7 7800X3D","RYZEN 5 7600X"],
        compatible=["RYZEN 9 9950X3D","RYZEN 9 9950X","RYZEN 9 9900X","RYZEN 7 9800X3D","RYZEN 7 9700X","RYZEN 5 9600X","RYZEN 9 7950X3D","RYZEN 9 7950X","RYZEN 7 7800X3D","RYZEN 9 7900X","RYZEN 7 7700X","RYZEN 5 7600X"],
    ),
    BoardEntry(
        match="Gigabyte X670 Aorus Elite AX",
        socket="AM5",
        support_url="https://www.gigabyte.com/Motherboard/X670-AORUS-ELITE-AX/support#support-cpu",
        board_note="X670 chipset, DDR5, dual PCIe 4.0 M.2.",
        preferred_with_gpu=["RYZEN 9 9900X","RYZEN 7 9800X3D","RYZEN 9 7950X"],
        preferred_without_gpu=["RYZEN 9 7950X3D","RYZEN 7 7800X3D","RYZEN 5 7600X"],
        compatible=["RYZEN 9 9950X3D","RYZEN 9 9950X","RYZEN 9 9900X","RYZEN 7 9800X3D","RYZEN 7 9700X","RYZEN 5 9600X","RYZEN 9 7950X3D","RYZEN 9 7950X","RYZEN 7 7800X3D","RYZEN 9 7900X","RYZEN 7 7700X","RYZEN 5 7600X"],
    ),
    # --- LGA1700 ---
    BoardEntry(
        match="ASUS ROG Maximus Z790 Hero",
        socket="LGA1700",
        support_url="https://rog.asus.com/motherboards/rog-maximus/rog-maximus-z790-hero-model/helpdesk_download/",
        board_note="Z790 chipset, supports 12th/13th/14th Gen Intel Core.",
        preferred_with_gpu=["I9-14900K","I9-13900K","I7-14700K","I7-13700K"],
        preferred_without_gpu=["I9-14900K","I9-13900K","I7-14700K","I5-14600K"],
        compatible=["I9-14900K","I9-14900F","I7-14700K","I7-14700F","I5-14600K","I5-14400F","I9-13900K","I7-13700K","I5-13600K","I9-12900K","I7-12700K","I5-12600K"],
    ),
    BoardEntry(
        match="MSI MAG B660 Tomahawk WiFi",
        socket="LGA1700",
        support_url="https://www.msi.com/Motherboard/MAG-B660-TOMAHAWK-WIFI-DDR4/support#cpu",
        board_note="B660 chipset, DDR4, supports 12th/13th Gen Intel Core.",
        preferred_with_gpu=["I7-12700K","I5-12600K","I7-13700K"],
        preferred_without_gpu=["I7-12700K","I5-12600K","I5-12400"],
        compatible=["I9-12900K","I7-12700K","I7-12700KF","I5-12600K","I5-12600KF","I5-12500","I5-12400F","I5-12400","I3-12100F","I3-12100"],
    ),
    BoardEntry(
        match="Gigabyte Z790 Aorus Elite AX",
        socket="LGA1700",
        support_url="https://www.gigabyte.com/Motherboard/Z790-AORUS-ELITE-AX/support#support-cpu",
        board_note="Z790 chipset, DDR5, supports 12th/13th/14th Gen Intel Core.",
        preferred_with_gpu=["I9-14900K","I9-13900K","I7-14700K","I7-13700K"],
        preferred_without_gpu=["I9-14900K","I7-14700K","I5-14600K"],
        compatible=["I9-14900K","I9-14900F","I7-14700K","I7-14700F","I5-14600K","I5-14400F","I9-13900K","I7-13700K","I5-13600K","I9-12900K","I7-12700K","I5-12600K"],
    ),
    # --- LGA1851 ---
    BoardEntry(
        match="ASUS ROG Maximus Z890 Hero",
        socket="LGA1851",
        support_url="https://rog.asus.com/motherboards/rog-maximus/rog-maximus-z890-hero-model/helpdesk_download/",
        board_note="Z890 chipset, supports Intel Core Ultra 200 series.",
        preferred_with_gpu=["CORE ULTRA 9 285K","CORE ULTRA 7 265K","CORE ULTRA 5 245K"],
        preferred_without_gpu=["CORE ULTRA 9 285K","CORE ULTRA 7 265K","CORE ULTRA 5 245K"],
        compatible=["CORE ULTRA 9 285K","CORE ULTRA 7 265K","CORE ULTRA 5 245K"],
    ),
    BoardEntry(
        match="MSI MAG B860 Tomahawk WiFi",
        socket="LGA1851",
        support_url="https://www.msi.com/Motherboard/MAG-B860-TOMAHAWK-WIFI/support#cpu",
        board_note="B860 chipset, DDR5, supports Intel Core Ultra 200 series.",
        preferred_with_gpu=["CORE ULTRA 7 265K","CORE ULTRA 5 245K"],
        preferred_without_gpu=["CORE ULTRA 7 265K","CORE ULTRA 5 245K"],
        compatible=["CORE ULTRA 9 285K","CORE ULTRA 7 265K","CORE ULTRA 5 245K"],
    ),
    # --- AM4 ---
    BoardEntry(
        match="ASUS ROG Crosshair VIII Hero",
        socket="AM4",
        support_url="https://rog.asus.com/motherboards/rog-crosshair/rog-crosshair-viii-hero-model/helpdesk_download/",
        board_note="X570 chipset, supports Ryzen 1000-5000 series.",
        preferred_with_gpu=["RYZEN 9 5950X","RYZEN 7 5800X3D","RYZEN 9 5900X"],
        preferred_without_gpu=["RYZEN 9 5950X","RYZEN 7 5800X3D","RYZEN 5 5600X"],
        compatible=["RYZEN 9 5950X","RYZEN 9 5900X","RYZEN 7 5800X3D","RYZEN 7 5800X","RYZEN 5 5600X"],
    ),
    BoardEntry(
        match="MSI MAG B550 Tomahawk",
        socket="AM4",
        support_url="https://www.msi.com/Motherboard/MAG-B550-TOMAHAWK/support#cpu",
        board_note="B550 chipset, supports Ryzen 3000-5000 series.",
        preferred_with_gpu=["RYZEN 7 5800X3D","RYZEN 9 5900X","RYZEN 7 5800X"],
        preferred_without_gpu=["RYZEN 7 5800X3D","RYZEN 5 5600X","RYZEN 7 5800X"],
        compatible=["RYZEN 9 5950X","RYZEN 9 5900X","RYZEN 7 5800X3D","RYZEN 7 5800X","RYZEN 5 5600X"],
    ),
    BoardEntry(
        match="Gigabyte B450 Aorus Elite",
        socket="AM4",
        support_url="https://www.gigabyte.com/Motherboard/B450-AORUS-ELITE/support#support-cpu",
        board_note="B450 chipset, supports Ryzen 2000-5000 series (BIOS update needed for 5000).",
        preferred_with_gpu=["RYZEN 7 5800X3D","RYZEN 9 5900X","RYZEN 7 5800X"],
        preferred_without_gpu=["RYZEN 5 5600X","RYZEN 7 5800X","RYZEN 7 5800X3D"],
        compatible=["RYZEN 9 5950X","RYZEN 9 5900X","RYZEN 7 5800X3D","RYZEN 7 5800X","RYZEN 5 5600X"],
    ),
]

CATALOG: list[BoardEntry] = sorted(_catalog, key=lambda e: len(e.match), reverse=True)


def find(board_name: str) -> BoardEntry | None:
    norm = _normalize(board_name)
    for entry in CATALOG:
        if _normalize(entry.match) in norm:
            return entry
    return None


def _normalize(value: str) -> str:
    import re
    v = value.upper()
    v = re.sub(r"[^A-Z0-9]+", " ", v)
    return v.strip()
