"""Offscreen render harness for fast visual iteration.

Usage:
    python _preview.py <out.png> [profile] [demo]

- Caches one real scan to _metrics_cache.json (so re-renders are instant).
- "demo" injects synthetic findings so the screenshot exercises chips,
  multiple severities, and 'buy' upgrades (with affiliate links).
"""
import json
import os
import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

OUT = sys.argv[1] if len(sys.argv) > 1 else "_preview.png"
PROFILE = sys.argv[2] if len(sys.argv) > 2 else "Gaming"
DEMO = "demo" in sys.argv[3:] or (len(sys.argv) > 3 and sys.argv[3] == "demo")

CACHE = "_metrics_cache.json"


def get_metrics():
    if os.path.isfile(CACHE):
        with open(CACHE, encoding="utf-8") as fh:
            return json.load(fh)
    from platforms import get_collector
    m = get_collector().collect()
    with open(CACHE, "w", encoding="utf-8") as fh:
        json.dump(m, fh, default=str)
    return m


def demo_tweaks(m):
    m = dict(m)
    m["ram_total_gb"] = 8
    m["ram_used_pct"] = 81
    m["sys_is_hdd"] = True
    m["has_ssd"] = False
    m["has_dedicated_gpu"] = False
    m["gpus"] = ["Intel UHD Graphics 630"]
    m["vram_gb"] = 0
    m["gpu_rank"] = 0
    m["gpu_driver_age_days"] = 800
    m["problem_device_count"] = 2
    m["problem_device_names"] = "Realtek High Definition Audio, PCI Device"
    m["startup_count"] = 14
    m["startup_names"] = "Steam, Discord, Spotify, OneDrive, Epic Games, NZXT CAM"
    m["last_update_days"] = 140
    m["disk_event_count"] = 1
    m.pop("cpu_upgrade", None)  # force recompute against the (real) board
    return m


app = QApplication(sys.argv)
from gui.main_window import MainWindow

metrics = get_metrics()
if DEMO:
    metrics = demo_tweaks(metrics)

w = MainWindow()
w.collector.collect = lambda: dict(metrics)
w.current_profile = PROFILE
w.resize(1200, 880)
w.show()


def grab():
    pm = w.grab()
    pm.save(OUT)
    print("saved", OUT, pm.width(), "x", pm.height())
    # Print the affiliate URLs that ended up on cards (proof of wiring).
    data = w.results.get(w.device_type, {}).get(w.current_profile, {})
    for cat in data.get("categories", []):
        up = getattr(cat, "upgrade", None)
        if up and getattr(up, "url", ""):
            print(f"  LINK [{cat.key}] {up.url}")
    app.quit()


QTimer.singleShot(1600, grab)
QTimer.singleShot(8000, app.quit)
app.exec()
