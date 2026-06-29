"""Scoring engine — ports the PowerShell Get-Result function.

Expects a flat metrics dict (from platform collector) and a Profile,
returns a ScanResult with 13 scored categories.
"""

from __future__ import annotations

from .profiles import get as get_profile
from .cpu_advisor import advise as cpu_advise
from utils.shopping import shop


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(v: float, lo=0, hi=100) -> int:
    return max(lo, min(hi, round(v)))


def _nf(severity: str, title: str, detail: str, action: str):
    from platforms.base import Finding
    return Finding(severity=severity, title=title, detail=detail, action=action)


def _score_hex(s: int) -> str:
    if s >= 80:
        return "#2DD4A7"
    if s >= 50:
        return "#F5C451"
    if s >= 30:
        return "#FF935C"
    return "#FF5C77"


def _upgrade(kind: str, text: str, url: str = "", note: str = ""):
    from platforms.base import Upgrade
    return Upgrade(kind=kind, text=text, url=url, note=note)


# ---------------------------------------------------------------------------
# Category scorers
# ---------------------------------------------------------------------------

def _score_memory(m: dict, p) -> tuple[int, list, object]:
    s = 100
    f: list = []

    # RAM capacity
    if m.get("ram_total_gb", 0) < p.ram_target_gb:
        short = (p.ram_target_gb - m["ram_total_gb"]) / p.ram_target_gb
        s -= round(80 * short)
        sev = "Critical" if m["ram_total_gb"] < p.ram_target_gb * 0.5 else (
            "High" if m["ram_total_gb"] < p.ram_target_gb * 0.75 else "Medium"
        )
        f.append(_nf(sev,
            f"Only {m['ram_total_gb']} GB RAM (this profile expects {p.ram_target_gb} GB+)",
            "Too little memory forces Windows to swap to disk, causing stutter and slow app switching.",
            f"Upgrade to at least {p.ram_target_gb} GB RAM - the single biggest real-world speed gain."))

    # RAM usage
    ram_used = m.get("ram_used_pct", 0)
    if ram_used >= 85:
        s -= p.mem_heavy_penalty
        f.append(_nf("High", f"Memory {ram_used}% used right now",
            "Very little free RAM; the system is under memory pressure.",
            "Close unused apps/browser tabs, or add RAM."))
    elif ram_used >= 70:
        s -= p.mem_med_penalty
        f.append(_nf("Medium", f"Memory {ram_used}% used right now",
            "Memory is filling up.", "Watch heavy apps; consider more RAM for headroom."))

    # Commit pressure
    commit = m.get("commit_used_pct", 0)
    if commit >= 85:
        s -= 10
        f.append(_nf("High", f"Virtual memory {commit}% committed",
            "Windows is close to exhausting RAM plus pagefile headroom.",
            "Close heavy apps, increase RAM, or check for a leaking process."))
    elif commit >= 75:
        s -= 5
        f.append(_nf("Medium", f"Virtual memory {commit}% committed",
            "The system is using a lot of total memory headroom.",
            "Watch for heavy apps or memory leaks."))

    # Top memory user
    top_gb = m.get("top_mem_gb", 0)
    if top_gb >= 3:
        s -= 5
        f.append(_nf("Low", f"Largest app is using {top_gb} GB RAM",
            f"Top memory users: {m.get('top_mem', 'N/A')}",
            "Close the app if that usage is unexpected."))

    # Upgrade suggestion
    ram_slots_used = m.get("ram_slots_used", "?")
    ram_slots_total = m.get("ram_slots_total", "")
    ram_type = m.get("ram_type", "RAM")
    ram_form = m.get("ram_form", "desktop")
    slot_note = (
        f"Slots used: {ram_slots_used}/{ram_slots_total}. Match type/speed; use a free slot or replace a stick."
        if ram_slots_total else "Match your current type/speed; use a free slot or replace a stick."
    )
    if m.get("ram_total_gb", 0) < p.ram_target_gb:
        fw = "SO-DIMM laptop" if ram_form == "laptop" else "DIMM desktop"
        ram_kind = ram_type if ram_type and ram_type != "RAM" else "DDR4"
        form_q = "laptop SO-DIMM" if ram_form == "laptop" else "desktop DIMM"
        up = _upgrade("buy",
            f"Add memory to reach {p.ram_target_gb} GB ({ram_type}, {fw})",
            url=shop(f"{ram_kind} {form_q} memory {p.ram_target_gb}GB"),
            note=slot_note)
    else:
        up = _upgrade("ok", "RAM is sufficient for this profile.", note=slot_note)

    from platforms.base import CategoryResult
    score = _clamp(s)
    cat = CategoryResult(
        key="memory", name="Memory (RAM)", icon="\U0001F9E0",
        score=score, weight=p.weights["memory"],
        stat=f"{m.get('ram_total_gb', '?')} GB - {ram_used}% in use",
        findings=f, upgrade=up if score < 85 else None,
    )
    return score, f, cat


def _score_storage(m: dict, p) -> tuple[int, list, object]:
    s = 100
    f: list = []

    sys_free_pct = m.get("sys_free_pct", 100)
    sys_free_gb = m.get("sys_free_gb", 0)
    sys_size_gb = m.get("sys_size_gb", 0)

    if sys_free_pct < 10:
        s -= 45
        f.append(_nf("Critical", f"System drive almost full ({sys_free_pct}% free)",
            f"{sys_free_gb} GB free of {sys_size_gb} GB. Windows slows badly below ~10% free.",
            "Free up space: Disk Cleanup, uninstall unused apps, move files off C:."))
    elif sys_free_pct < p.free_pct_target:
        s -= 20
        f.append(_nf("Medium", f"System drive low on space ({sys_free_pct}% free)",
            f"{sys_free_gb} GB free. This profile wants {p.free_pct_target}%+ headroom.",
            "Clear space to give Windows breathing room."))

    temp_gb = m.get("temp_gb", 0)
    if temp_gb >= 2:
        s -= 15
        f.append(_nf("Medium", f"{temp_gb} GB of temp/junk files",
            "Temp folders are bloated.", "Run Disk Cleanup (cleanmgr) or the Cleanup launcher."))
    elif temp_gb >= 1:
        s -= 8
        f.append(_nf("Low", f"{temp_gb} GB of temp files",
            "Minor junk buildup.", "Optional cleanup."))

    recycle_gb = m.get("recycle_gb", 0)
    if recycle_gb >= 5:
        s -= 8
        f.append(_nf("Low", f"Recycle Bin holding {recycle_gb} GB",
            "Deleted files still using disk space.", "Empty the Recycle Bin."))

    # Upgrade
    score = _clamp(s)
    if sys_free_pct < p.free_pct_target:
        up = _upgrade("buy", "Add a larger SSD for more space",
            url=shop("internal SSD 2TB"),
            note="Try the free cleanup first - you may not need to buy anything.")
    elif temp_gb >= 1:
        up = _upgrade("free", "Clear junk/temp files - free, no purchase needed.")
    else:
        up = _upgrade("ok", "Plenty of space for this profile.")

    from platforms.base import CategoryResult
    cat = CategoryResult(
        key="storage", name="Storage Space", icon="\U0001F4BE",
        score=score, weight=p.weights["storage"],
        stat=f"{sys_free_gb} GB free of {sys_size_gb} GB",
        findings=f, upgrade=up if score < 85 else None,
    )
    return score, f, cat


def _score_diskspeed(m: dict, p) -> tuple[int, list, object]:
    s = 100
    f: list = []

    # Bad disk health
    bad = m.get("disk_health_bad", [])
    if bad:
        s -= 60
        f.append(_nf("Critical", "Drive reporting poor health",
            f"SMART status: {', '.join(bad)}",
            "BACK UP NOW. A failing drive can lose data. Replace it."))

    sys_is_hdd = m.get("sys_is_hdd", False)
    has_ssd = m.get("has_ssd", False)
    secondary_hdds = m.get("secondary_hdds", [])
    is_laptop = m.get("is_laptop", False)

    if sys_is_hdd:
        s -= p.hdd_sys_penalty
        sev = "Critical" if p.hdd_sys_penalty >= 70 else "High"
        f.append(_nf(sev, "Windows runs on a mechanical hard drive (HDD)",
            "Spinning drives are 5-10x slower than SSDs - throttling boot, app launches and load times.",
            "Clone Windows onto an SSD. For this profile it's essential."))
    elif has_ssd:
        f.append(_nf("Info", "System drive is a solid-state drive (SSD)",
            "Fast storage for the OS.", ""))

    for h in secondary_hdds:
        if p.hdd_sec_penalty > 0:
            s -= p.hdd_sec_penalty
            f.append(_nf("Medium", f"Secondary drive is mechanical: {h}",
                "Loading projects/games from an HDD is slow for this profile.",
                "Move active work to an SSD."))
        else:
            f.append(_nf("Low", f"Secondary drive is mechanical: {h}",
                "Fine for bulk storage.", "Only matters if you run programs from it."))

    disk_busy = m.get("disk_busy_pct", 0)
    if disk_busy >= 90:
        s -= 20
        f.append(_nf("High", f"Disk is saturated right now ({disk_busy}% busy)",
            "A pegged disk makes the whole PC feel frozen.",
            "Open Task Manager -> Processes and sort by Disk to find the culprit."))
    elif disk_busy >= 70:
        s -= 10
        f.append(_nf("Medium", f"Disk is busy right now ({disk_busy}%)",
            "Heavy background disk activity can cause stutter.",
            "Wait for updates/indexing to finish or check Task Manager for disk-heavy apps."))

    if m.get("trim_disabled") and has_ssd:
        s -= 10
        f.append(_nf("Medium", "SSD TRIM appears disabled",
            "TRIM helps SSDs keep write performance healthy over time.",
            "Run an elevated prompt and check fsutil behavior query DisableDeleteNotify; enable TRIM if appropriate."))

    score = _clamp(s)
    dstat = "Boot drive: HDD (slow)" if sys_is_hdd else ("Boot drive: SSD" if has_ssd else "Boot drive: unknown")
    if sys_is_hdd:
        up = _upgrade("buy", "Replace the boot drive with an SSD",
            url=shop("2.5 inch SATA SSD 1TB" if is_laptop else "NVMe M.2 SSD 1TB"),
            note="A 2.5\" SATA SSD fits almost any PC/laptop. Desktops with an M.2 slot can use a faster NVMe SSD for similar money.")
    elif secondary_hdds and p.hdd_sec_penalty > 0:
        up = _upgrade("buy", "Add an SSD for your active games/projects",
            url=shop("NVMe M.2 SSD 2TB"),
            note="Keep the HDD for bulk storage; run active work off the SSD.")
    else:
        up = _upgrade("ok", "Already running on an SSD.")

    from platforms.base import CategoryResult
    cat = CategoryResult(
        key="diskspeed", name="Disk Speed & Health", icon="⚡",
        score=score, weight=p.weights["diskspeed"],
        stat=dstat, findings=f, upgrade=up if score < 85 else None,
    )
    return score, f, cat


def _score_cpu(m: dict, p) -> tuple[int, list, object]:
    s = 100
    f: list = []

    cores = m.get("cpu_cores", 0)
    if cores < p.core_target:
        short = (p.core_target - cores) / p.core_target
        s -= round(55 * short)
        f.append(_nf("Medium", f"{cores}-core CPU (profile favours {p.core_target}+ cores)",
            "Fewer cores limit heavy multitasking and demanding apps.",
            "A CPU upgrade helps if you regularly max it out."))

    cpu_load = m.get("cpu_load_pct", 0)
    if cpu_load >= 85:
        s -= 15
        f.append(_nf("High", f"CPU heavily loaded right now ({cpu_load}%)",
            f"Sustained load. Top processes: {m.get('top_cpu', 'N/A')}",
            f"Check Task Manager; close/investigate {m.get('top_cpu', 'N/A')} if unexpected."))
    elif cpu_load >= 70:
        s -= 8
        f.append(_nf("Low", f"CPU busy ({cpu_load}%)",
            f"Moderate load from: {m.get('top_cpu', 'N/A')}",
            "Normal if actively using heavy apps."))

    clock_pct = m.get("cpu_clock_pct", 0)
    max_mhz = m.get("cpu_max_mhz", 0)
    cur_mhz = m.get("cpu_current_mhz", 0)
    if clock_pct > 0 and cpu_load >= 70 and clock_pct < 60:
        s -= 10
        f.append(_nf("Medium", "CPU clock is low while busy",
            f"{cur_mhz} MHz current vs. {max_mhz} MHz max.",
            "Check power plan, temperatures, laptop AC power, and cooling."))

    cpu_rank = m.get("cpu_rank", 0)
    rank_text = f" Hardware tier: {cpu_rank}/1000." if cpu_rank else ""
    board_name = m.get("board_name", "unknown")
    cpu_socket = m.get("cpu_socket", "not exposed")
    f.append(_nf("Info", f"Processor: {m.get('cpu_name', 'Unknown')}",
        f"Board: {board_name}; socket/platform: {cpu_socket}.{rank_text}", ""))

    # Upgrade
    advice = m.get("cpu_upgrade", {})
    has_better = bool(advice.get("recommended") and advice.get("rank") and
                      cpu_rank and advice["rank"] > cpu_rank)
    needs_upgrade = cores < p.core_target or cpu_load >= 85 or has_better

    if needs_upgrade and advice.get("can_buy") and advice.get("query"):
        text = advice["text"] if (cores < p.core_target or cpu_load >= 85) else (
            f"Optional CPU upgrade: {advice['recommended']}"
        )
        up = _upgrade("buy", text, url=shop(advice["query"]), note=advice.get("note", ""))
    elif advice.get("can_buy") and advice.get("query"):
        up = _upgrade("buy", advice["text"], url=shop(advice["query"]), note=advice.get("note", ""))
    elif advice.get("text"):
        up = _upgrade("advisory", advice["text"], note=advice.get("note", ""))
    else:
        up = _upgrade("ok", "CPU is adequate for this profile.", note=advice.get("note", ""))

    from platforms.base import CategoryResult
    score = _clamp(s)
    cat = CategoryResult(
        key="cpu", name="CPU", icon="\U0001F525",
        score=score, weight=p.weights["cpu"],
        stat=f"{cores} cores / {m.get('cpu_threads', '?')} threads",
        findings=f, upgrade=up if score < 85 else None,
    )
    return score, f, cat


def _score_gpu(m: dict, p) -> tuple[int, list, object]:
    s = 100
    f: list = []

    gpus = m.get("gpus", [])
    if not gpus:
        s -= 30
        f.append(_nf("High", "No graphics controller detected",
            "Windows did not report a GPU/display controller.",
            "Install chipset/graphics drivers from the PC or GPU maker."))

    has_dgpu = m.get("has_dedicated_gpu", False)
    is_laptop = m.get("is_laptop", False)

    if p.need_gpu and not has_dgpu:
        if is_laptop:
            s -= 30
            f.append(_nf("High", "Integrated graphics only (laptop)",
                "Integrated laptop graphics struggle with modern games and GPU-accelerated creative work - and a laptop can't take a desktop graphics card.",
                "Choose a laptop with a dedicated GPU, or add an external GPU (eGPU) over Thunderbolt/USB4."))
        else:
            s -= 55
            f.append(_nf("High", "No dedicated graphics card detected",
                "Integrated graphics struggle with modern games and GPU-accelerated creative work.",
                "Add a dedicated GPU for real gaming performance."))
    elif has_dgpu and m.get("vram_gb", 0) > 0 and m["vram_gb"] < p.gpu_vram_target:
        s -= 20
        note = "Lower texture settings; a laptop GPU can't be upgraded." if is_laptop else "Lower texture settings or upgrade the GPU."
        f.append(_nf("Medium", f"GPU has about {m['vram_gb']} GB VRAM",
            f"This profile is happier with {p.gpu_vram_target}+ GB VRAM.", note))

    driver_age = m.get("gpu_driver_age_days", 0)
    if driver_age > 730:
        s -= 18
        f.append(_nf("High", "Graphics driver is over 2 years old",
            "Old GPU drivers can cause stutter, crashes, and poor game/app performance.",
            "Install the latest driver from NVIDIA, AMD, Intel, or the PC maker."))
    elif driver_age > 365:
        s -= 8
        f.append(_nf("Medium", "Graphics driver is over 1 year old",
            "Driver updates often improve stability and performance.",
            "Update the GPU driver."))

    if m.get("gpu_problem_count", 0) > 0:
        s -= 25
        f.append(_nf("High", f"{m['gpu_problem_count']} GPU device problem(s)",
            "Device Manager reports an error for a graphics device.",
            "Open Device Manager and repair/reinstall the graphics driver."))

    if gpus:
        gpu_rank = m.get("gpu_rank", 0)
        rank_str = f"; hardware tier: {gpu_rank}/1000" if gpu_rank else ""
        f.append(_nf("Info", f"Graphics: {', '.join(gpus)}",
            f"Detected VRAM: {m.get('vram_gb', '?')} GB{rank_str}", ""))

    score = _clamp(s)
    if p.need_gpu and not has_dgpu:
        if is_laptop:
            up = _upgrade("advisory", "A laptop can't take a desktop graphics card",
                note="Laptop graphics are built in and not replaceable. For more GPU power, pick a laptop with a dedicated GPU, or use an external GPU (eGPU) enclosure over Thunderbolt/USB4.")
        else:
            up = _upgrade("buy", "Add a dedicated graphics card",
                url=shop(f"desktop graphics card {p.gpu_vram_target}GB"),
                note="Check power-supply wattage, case clearance, and for a free PCIe x16 slot before buying.")
    elif has_dgpu and m.get("vram_gb", 0) > 0 and m["vram_gb"] < p.gpu_vram_target:
        if is_laptop:
            up = _upgrade("advisory", "Limited VRAM - not upgradeable on a laptop",
                note="A laptop's GPU is fixed. Lower texture/resolution settings; a newer laptop with more VRAM is the real upgrade.")
        else:
            up = _upgrade("buy", f"Upgrade to a GPU with {p.gpu_vram_target}+ GB VRAM",
                url=shop(f"desktop graphics card {p.gpu_vram_target}GB"),
                note="Check PSU wattage, connector type, physical length, and case clearance.")
    elif driver_age > 365:
        up = _upgrade("free", "Update the graphics driver - free first step.")
    else:
        up = _upgrade("ok", "GPU looks adequate for this profile.")

    from platforms.base import CategoryResult
    cat = CategoryResult(
        key="gpu", name="Graphics (GPU)", icon="\U0001F3AE",
        score=score, weight=p.weights["gpu"],
        stat=("Dedicated GPU detected" if has_dgpu else
              ("Integrated graphics" if gpus else "GPU unknown")),
        findings=f, upgrade=up if score < 85 else None,
    )
    return score, f, cat


def _score_startup(m: dict, p) -> tuple[int, list, object]:
    s = 100
    f: list = []

    count = m.get("startup_count", 0)
    over = max(0, count - p.start_threshold)
    if over > 0:
        s -= over * p.start_penalty_per
        sev = "High" if over >= 5 else "Medium"
        f.append(_nf("High" if over >= 5 else "Medium", f"{count} programs launch at boot",
            f"Background autostarts slow login and eat RAM/CPU: {m.get('startup_names', 'N/A')}",
            "Task Manager -> Startup tab -> disable what you don't need at boot."))

    uptime_days = m.get("uptime_days", 0)
    if uptime_days >= 14:
        s -= 12
        f.append(_nf("Medium", f"Up for {round(uptime_days)} days without restart",
            "Long uptime can leave driver/app leaks around.",
            "Restart to refresh drivers and memory."))
    elif uptime_days >= 7:
        s -= 8
        f.append(_nf("Low", f"Up for {round(uptime_days)} days without restart",
            "Long uptime causes memory fragmentation/leaks.",
            "A restart often restores responsiveness."))

    up = _upgrade("free", "No purchase needed - disable startup apps and restart regularly.")
    from platforms.base import CategoryResult
    cat = CategoryResult(
        key="startup", name="Startup & Boot", icon="\U0001F680",
        score=_clamp(s), weight=p.weights["startup"],
        stat=f"{count} startup apps", findings=f,
        upgrade=up if _clamp(s) < 85 else None,
    )
    return _clamp(s), f, cat


def _score_background(m: dict, p) -> tuple[int, list, object]:
    s = 100
    f: list = []

    svc = m.get("third_party_service_count", 0)
    if svc > p.service_threshold + 12:
        s -= 22
        f.append(_nf("High", f"{svc} third-party auto services running",
            f"Always-on services consume boot time, RAM, and CPU. Examples: {m.get('third_party_service_names', 'N/A')}",
            "Uninstall software you no longer use; set nonessential services to manual."))
    elif svc > p.service_threshold:
        s -= 12
        f.append(_nf("Medium", f"{svc} third-party auto services running",
            "A busy background-service stack can make a PC feel sluggish.",
            "Review installed vendor utilities and updaters."))

    tasks = m.get("scheduled_task_count", 0)
    if tasks > p.task_threshold + 8:
        s -= 18
        f.append(_nf("High", f"{tasks} non-Microsoft scheduled tasks",
            "Scheduled updaters and helpers can wake the PC and run in bursts.",
            "Open Task Scheduler and disable tasks you recognize as unnecessary."))
    elif tasks > p.task_threshold:
        s -= 9
        f.append(_nf("Medium", f"{tasks} non-Microsoft scheduled tasks",
            "Background maintenance tasks may be adding overhead.",
            "Review third-party scheduled tasks."))

    top_cpu = m.get("top_cpu", "")
    if top_cpu:
        f.append(_nf("Info", f"Top CPU-time processes: {top_cpu}", "", ""))
    top_mem = m.get("top_mem", "")
    if top_mem:
        f.append(_nf("Info", f"Top memory users: {top_mem}", "", ""))

    up = _upgrade("free", "No purchase needed - remove bloat, disable unneeded helpers, and uninstall unused apps.")
    from platforms.base import CategoryResult
    cat = CategoryResult(
        key="background", name="Background Apps", icon="⚙",
        score=_clamp(s), weight=p.weights["background"],
        stat=f"{svc} services / {tasks} tasks",
        findings=f, upgrade=up if _clamp(s) < 85 else None,
    )
    return _clamp(s), f, cat


def _score_power(m: dict, p) -> tuple[int, list, object]:
    s = 100
    f: list = []

    if m.get("power_saver", False):
        s -= p.power_penalty
        f.append(_nf("Medium", "Power plan set to 'Power saver'",
            "This throttles the CPU/GPU to save energy.",
            "Switch to Balanced/High performance when speed matters."))

    if m.get("on_battery", False):
        s -= 10
        f.append(_nf("Low", "Laptop is running on battery",
            "Many laptops reduce CPU/GPU boost on battery power.",
            "Plug in AC power for best performance."))

    temp = m.get("thermal_temp_c", 0)
    if temp >= 90:
        s -= 35
        f.append(_nf("Critical", f"Thermal zone is very hot ({temp} C)",
            "Heat can force severe throttling and sudden shutdowns.",
            "Clean dust, check fans, improve airflow, and refresh thermal paste if needed."))
    elif temp >= 80:
        s -= 18
        f.append(_nf("High", f"Thermal zone is hot ({temp} C)",
            "Heat may be reducing boost clocks.",
            "Clean vents/fans and improve airflow."))

    if 0 < (clock_pct := m.get("cpu_clock_pct", 0)):
        cpu_load = m.get("cpu_load_pct", 0)
        if cpu_load >= 70 and clock_pct < 60:
            s -= 15
            f.append(_nf("High", "Possible throttling under load",
                f"CPU is busy but running at only {clock_pct}% of reported max clock.",
                "Check thermals, power plan, laptop charger, and BIOS power limits."))

    if not f:
        plan = m.get("power_plan", "Unknown")
        therm = f"Thermal zone max: {temp} C" if temp else "No thermal sensor exposed by Windows."
        f.append(_nf("Info", f"Power plan: {plan}", therm, ""))

    if temp >= 80:
        up = _upgrade("buy", "Improve cooling",
            url=shop("laptop cooling pad" if m.get("is_laptop") else "CPU air cooler"),
            note="Clean dust and verify fans first; cooling purchases only help if heat is the bottleneck.")
    else:
        up = _upgrade("free", "Use Balanced/High performance and keep vents clean.")

    from platforms.base import CategoryResult
    cat = CategoryResult(
        key="power", name="Power & Thermals", icon="\U0001F321",
        score=_clamp(s), weight=p.weights["power"],
        stat=f"Plan: {m.get('power_plan', 'Unknown')}",
        findings=f, upgrade=up if _clamp(s) < 85 else None,
    )
    return _clamp(s), f, cat


def _score_drivers(m: dict, p) -> tuple[int, list, object]:
    s = 100
    f: list = []

    prob = m.get("problem_device_count", 0)
    if prob > 0:
        s -= min(45, 15 * prob)
        f.append(_nf("High", f"{prob} device problem(s)",
            f"Device Manager is reporting errors: {m.get('problem_device_names', 'N/A')}",
            "Install/reinstall drivers from the PC, motherboard, or device maker."))

    old = m.get("old_driver_count", 0)
    if old > 12:
        s -= 20
        f.append(_nf("Medium", f"{old} important drivers are 5+ years old",
            f"Old storage, network, chipset, audio, or display drivers can cause lag and instability. Examples: {m.get('old_driver_names', 'N/A')}",
            "Update chipset, storage, network, and GPU drivers from vendor sources."))
    elif old > 0:
        s -= 8
        f.append(_nf("Low", f"{old} important driver(s) are 5+ years old",
            f"Some key drivers are old. Examples: {m.get('old_driver_names', 'N/A')}",
            "Check vendor driver updates if you see performance or stability issues."))

    bios_age = m.get("bios_age_days", 0)
    if bios_age and bios_age > 1825:
        s -= 8
        f.append(_nf("Low", "BIOS/UEFI is over 5 years old",
            "Old firmware can limit CPU support, stability, sleep behavior, and device compatibility.",
            "Check the motherboard/PC maker support page. Read the instructions carefully before flashing BIOS."))

    if not f:
        f.append(_nf("Info", "No obvious device/driver problems found",
            "Device Manager errors and very old key drivers were not detected.", ""))

    up = _upgrade("free",
        "Update drivers and BIOS from vendor support pages before buying hardware.",
        note="For CPU upgrades, the BIOS support list matters as much as the physical socket.")

    from platforms.base import CategoryResult
    cat = CategoryResult(
        key="drivers", name="Drivers & Devices", icon="\U0001F527",
        score=_clamp(s), weight=p.weights["drivers"],
        stat=(f"{prob} device errors" if prob else "No device errors"),
        findings=f, upgrade=up if _clamp(s) < 85 else None,
    )
    return _clamp(s), f, cat


def _score_updates(m: dict, p) -> tuple[int, list, object]:
    s = 100
    f: list = []

    if m.get("reboot_pending", False):
        s -= 18
        f.append(_nf("Medium", "A restart is pending",
            "Updates are half-applied and waiting on a reboot.",
            "Save work and restart."))

    last_days = m.get("last_update_days")
    if last_days is None:
        s -= 8
        f.append(_nf("Low", "Last successful Windows update unknown",
            "Windows did not report a recent successful update time.",
            "Open Windows Update and check for updates."))
    elif last_days > 120:
        s -= 28
        f.append(_nf("High", f"Windows updates are {last_days} days behind",
            "Very stale updates can mean missing performance, security, and driver fixes.",
            "Run Windows Update until fully current."))
    elif last_days > p.update_days_threshold:
        s -= 12
        f.append(_nf("Medium", f"Windows updates are {last_days} days behind",
            "The PC may be missing cumulative fixes and drivers.",
            "Run Windows Update."))

    stopped = m.get("update_services_stopped", [])
    if stopped:
        s -= 18
        f.append(_nf("High", f"Update service(s) stopped: {', '.join(stopped)}",
            "Windows Update/BITS being stopped can block fixes and driver delivery.",
            "Set Windows Update and BITS back to their normal startup behavior."))

    if not f:
        ts = f"Last successful install: {last_days} days ago." if last_days is not None else ""
        f.append(_nf("Info", "Windows update state looks normal", ts, ""))

    up = _upgrade("free", "No purchase needed - restart and run Windows Update.")
    from platforms.base import CategoryResult
    cat = CategoryResult(
        key="updates", name="Windows Updates", icon="\U0001F504",
        score=_clamp(s), weight=p.weights["updates"],
        stat=(f"Updated {last_days}d ago" if last_days is not None else "Update age unknown"),
        findings=f, upgrade=up if _clamp(s) < 85 else None,
    )
    return _clamp(s), f, cat


def _score_network(m: dict, p) -> tuple[int, list, object]:
    s = 100
    f: list = []

    net_mbps = m.get("net_link_mbps", 0)
    if 0 < net_mbps < 100:
        s -= 15
        f.append(_nf("Medium", "Network link is under 100 Mbps",
            "Slow link speed can make web, cloud, and game downloads feel like a PC problem.",
            "Use a better Wi-Fi band, Ethernet, or check router/adapter settings."))

    wifi = m.get("wifi_signal_pct", 0)
    if wifi > 0 and wifi < 55:
        s -= 18
        f.append(_nf("Medium", f"Wi-Fi signal is weak ({wifi}%)",
            "Weak signal causes stalls and retry delays.",
            "Move closer to the router, use 5/6 GHz when close, or use Ethernet."))

    ext = m.get("browser_ext_count", 0)
    if ext > p.browser_ext_threshold + 10:
        s -= 20
        f.append(_nf("High", f"{ext} browser extensions detected",
            "Extensions can slow page loads, inject scripts, and consume memory.",
            "Disable/remove extensions you do not actively use."))
    elif ext > p.browser_ext_threshold:
        s -= 10
        f.append(_nf("Medium", f"{ext} browser extensions detected",
            "A large extension stack can make browsers feel slow.",
            "Review Chrome/Edge/Firefox extensions."))

    cache_gb = m.get("browser_cache_gb", 0)
    if cache_gb > p.browser_cache_threshold + 3:
        s -= 10
        f.append(_nf("Low", f"{cache_gb} GB browser cache",
            "Huge caches can waste disk and occasionally slow profile startup.",
            "Clear browser cache if the browser feels sluggish."))
    elif cache_gb > p.browser_cache_threshold:
        s -= 5
        f.append(_nf("Low", f"{cache_gb} GB browser cache",
            "Some cleanup opportunity.", "Clear cache if needed."))

    if not f:
        names = m.get("network_names", "")
        f.append(_nf("Info", "Network/browser checks look normal",
            f"Active adapters: {names if names else 'unknown'}", ""))

    up = _upgrade("free", "No purchase needed - prune extensions, clear cache, and improve Wi-Fi/Ethernet first.")
    from platforms.base import CategoryResult
    cat = CategoryResult(
        key="network", name="Network & Browser", icon="\U0001F310",
        score=_clamp(s), weight=p.weights["network"],
        stat=(f"{net_mbps} Mbps link" if net_mbps else "Network link unknown"),
        findings=f, upgrade=up if _clamp(s) < 85 else None,
    )
    return _clamp(s), f, cat


def _score_stability(m: dict, p) -> tuple[int, list, object]:
    s = 100
    f: list = []

    disk_ev = m.get("disk_event_count", 0)
    if disk_ev > 0:
        s -= 30
        f.append(_nf("High", f"{disk_ev} disk/storage error(s) in 7 days",
            "Storage errors can cause freezes, retries, and data loss.",
            "Back up important data, check drive health, cables, and storage drivers."))

    whea = m.get("whea_event_count", 0)
    if whea > 0:
        s -= 25
        f.append(_nf("High", f"{whea} hardware error(s) in 7 days",
            "WHEA errors can point to CPU/RAM/PCIe instability, heat, or overclocking problems.",
            "Remove overclocks, check thermals, update BIOS/chipset, and test RAM."))

    bsod = m.get("bug_check_count", 0)
    if bsod > 0:
        s -= 25
        f.append(_nf("High", f"{bsod} blue-screen event(s) in 7 days",
            "Crashes can leave the PC unstable and often trace back to drivers/hardware.",
            "Update drivers and review Reliability Monitor."))

    app = m.get("app_crash_count", 0)
    if app > 5:
        s -= 12
        f.append(_nf("Medium", f"{app} app crash/hang events",
            "Frequent app crashes can feel like general slowness.",
            "Update or reinstall the crashing apps; check Reliability Monitor for names."))

    sys_errors = m.get("system_error_count", 0)
    if sys_errors > 40:
        s -= 8
        f.append(_nf("Low", f"{sys_errors} system error events in 7 days",
            "Lots of recent errors can hint at driver or hardware trouble.",
            "Open Event Viewer or Reliability Monitor for the repeating source."))

    if not f:
        f.append(_nf("Info", "No major recent stability signals",
            "No recent disk, WHEA, blue-screen, or heavy app-crash pattern was detected.", ""))

    up = _upgrade("free",
        "No purchase first - back up, update drivers, remove overclocks, and inspect Reliability Monitor.")
    from platforms.base import CategoryResult
    cat = CategoryResult(
        key="stability", name="Stability Logs", icon="\U0001F4C8",
        score=_clamp(s), weight=p.weights["stability"],
        stat=f"{sys_errors} system errors / 7d",
        findings=f, upgrade=up if _clamp(s) < 85 else None,
    )
    return _clamp(s), f, cat


def _score_security(m: dict, p) -> tuple[int, list, object]:
    s = 100
    f: list = []

    if not m.get("av_enabled", True):
        s -= 50
        f.append(_nf("Critical", "Antivirus appears disabled",
            "No active virus protection detected.",
            "Turn on Windows Security or install a reputable AV now."))

    if not m.get("realtime_protection", True):
        s -= 20
        f.append(_nf("High", "Real-time protection is off",
            "Threats can run before any scan catches them.",
            "Enable real-time protection in Windows Security."))

    defs_age = m.get("defs_age_days", 0)
    if defs_age > 30:
        s -= 25 if defs_age > 7 else p.defs_low_penalty
        sev = "High" if defs_age > 30 else "Medium"
        f.append(_nf(sev, f"Virus definitions {defs_age} days old",
            "Outdated signatures." if defs_age <= 30 else "Badly outdated; misses new threats.",
            "Update definitions (Virus & threat protection)."))

    sus = m.get("suspicious_count", 0)
    if sus > 0:
        s -= min(50, sus * 10)
        items = m.get("suspicious_list", [])
        review = " || ".join(str(x) for x in items[:5])
        f.append(_nf("High", f"{sus} suspicious file(s) in high-risk locations",
            f"Review: {review}",
            "Don't run them. Right-click -> Scan with Windows Security or check virustotal.com."))

    hosts = m.get("hosts_custom_entries", 0)
    if hosts > 0:
        s -= 8
        f.append(_nf("Medium", f"Hosts file has {hosts} custom entry(ies)",
            "Malware sometimes edits this to hijack sites.",
            "Review the hosts file; remove unknown lines."))

    if not f:
        f.append(_nf("Info", "No obvious security problems found",
            "Defender active, definitions current, no flagged files.", ""))

    up = _upgrade("free",
        "No purchase needed - update Defender and remove flagged files (all free).")
    from platforms.base import CategoryResult
    cat = CategoryResult(
        key="security", name="Security & Malware", icon="\U0001F6E1",
        score=_clamp(s), weight=p.weights["security"],
        stat=("No threats flagged" if not sus else f"{sus} files flagged"),
        findings=f, upgrade=up if _clamp(s) < 85 else None,
    )
    return _clamp(s), f, cat


# ---------------------------------------------------------------------------
# Main evaluate()
# ---------------------------------------------------------------------------

def evaluate(metrics: dict, profile_key: str, is_laptop: bool) -> dict:
    """Run all 13 category scorers and return a ScanResult-ready dict."""
    p = get_profile(profile_key)
    rows = []
    m = metrics

    # CPU upgrade advice needs to be pre-computed by the platform layer,
    # but we handle it here as a fallback.
    if "cpu_upgrade" not in m:
        board = m.get("board_name", "")
        socket = m.get("cpu_socket", "")
        m["cpu_upgrade"] = cpu_advise(
            m.get("cpu_name", ""), board, socket,
            m.get("has_dedicated_gpu", False), is_laptop,
        )

    scorers = [
        _score_memory, _score_storage, _score_diskspeed,
        _score_cpu, _score_gpu, _score_startup, _score_background,
        _score_power, _score_drivers, _score_updates,
        _score_network, _score_stability, _score_security,
    ]

    cats = []
    wsum = wnum = 0.0
    minc = 100

    for fn in scorers:
        sc, findings, cat = fn(m, p)
        cats.append(cat)
        wsum += p.weights[cat.key]
        wnum += sc * p.weights[cat.key]
        if sc < minc:
            minc = sc

    wavg = wnum / wsum if wsum > 0 else 0
    overall = _clamp(round(0.7 * wavg + 0.3 * minc))

    grade = (
        "A" if overall >= 90 else
        "B" if overall >= 80 else
        "C" if overall >= 70 else
        "D" if overall >= 55 else
        "F"
    )
    grade_label = {
        "A": "Excellent", "B": "Good", "C": "Fair",
        "D": "Poor", "F": "Needs serious work",
    }[grade]

    return {
        "profile": p.name,
        "blurb": p.blurb,
        "overall": overall,
        "grade": grade,
        "grade_label": grade_label,
        "categories": cats,
    }
