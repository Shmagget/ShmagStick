"""Three scoring profiles: Everyday, Gaming, Workstation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    key: str
    name: str
    blurb: str
    ram_target_gb: int
    free_pct_target: int
    hdd_sys_penalty: int
    hdd_sec_penalty: int
    start_threshold: int
    start_penalty_per: int
    core_target: int
    mem_heavy_penalty: int
    mem_med_penalty: int
    need_gpu: bool
    gpu_vram_target: int
    power_penalty: int
    service_threshold: int
    task_threshold: int
    browser_ext_threshold: int
    browser_cache_threshold: float
    update_days_threshold: int
    weights: dict[str, int]
    defs_low_penalty: int = 12
    defs_high_penalty: int = 25


PROFILES: dict[str, Profile] = {
    "Everyday": Profile(
        key="Everyday",
        name="Everyday",
        blurb="Web, email, office and streaming. Balanced expectations.",
        ram_target_gb=8,
        free_pct_target=15,
        hdd_sys_penalty=45,
        hdd_sec_penalty=0,
        start_threshold=8,
        start_penalty_per=4,
        core_target=2,
        mem_heavy_penalty=15,
        mem_med_penalty=6,
        need_gpu=False,
        gpu_vram_target=1,
        power_penalty=7,
        service_threshold=18,
        task_threshold=10,
        browser_ext_threshold=12,
        browser_cache_threshold=2,
        update_days_threshold=45,
        weights={
            "memory": 13, "storage": 9, "diskspeed": 12, "startup": 8,
            "background": 7, "cpu": 8, "gpu": 4, "power": 7,
            "drivers": 7, "updates": 5, "network": 5,
            "stability": 7, "security": 8,
        },
    ),
    "Gaming": Profile(
        key="Gaming",
        name="Gaming",
        blurb="Modern games at high, stable frame rates. Demands fast storage, RAM, CPU headroom and a real GPU.",
        ram_target_gb=16,
        free_pct_target=15,
        hdd_sys_penalty=70,
        hdd_sec_penalty=5,
        start_threshold=5,
        start_penalty_per=6,
        core_target=6,
        mem_heavy_penalty=20,
        mem_med_penalty=10,
        need_gpu=True,
        gpu_vram_target=6,
        power_penalty=15,
        service_threshold=14,
        task_threshold=8,
        browser_ext_threshold=10,
        browser_cache_threshold=2,
        update_days_threshold=60,
        weights={
            "memory": 13, "storage": 8, "diskspeed": 12, "startup": 6,
            "background": 7, "cpu": 12, "gpu": 15, "power": 8,
            "drivers": 6, "updates": 3, "network": 2,
            "stability": 4, "security": 4,
        },
    ),
    "Workstation": Profile(
        key="Workstation",
        name="Workstation",
        blurb="Rendering, compiling, VMs and heavy multitasking. Strictest profile.",
        ram_target_gb=32,
        free_pct_target=20,
        hdd_sys_penalty=85,
        hdd_sec_penalty=15,
        start_threshold=5,
        start_penalty_per=6,
        core_target=8,
        mem_heavy_penalty=22,
        mem_med_penalty=12,
        need_gpu=False,
        gpu_vram_target=4,
        power_penalty=15,
        service_threshold=16,
        task_threshold=8,
        browser_ext_threshold=10,
        browser_cache_threshold=3,
        update_days_threshold=45,
        weights={
            "memory": 15, "storage": 7, "diskspeed": 11, "startup": 5,
            "background": 8, "cpu": 15, "gpu": 6, "power": 8,
            "drivers": 7, "updates": 5, "network": 2,
            "stability": 5, "security": 6,
        },
    ),
}


def get(key: str) -> Profile:
    return PROFILES[key]
