"""macOS metric collector."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timedelta

import psutil

from platforms.base import MetricCollector


def _run(cmd: list[str], timeout: int = 10) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def _run_json(cmd: list[str]) -> dict | list:
    out = _run(cmd)
    if not out:
        return {}
    try:
        return json.loads(out)
    except Exception:
        return {}


def _try(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


class MacOSCollector(MetricCollector):
    def collect(self) -> dict:
        m: dict = {}
        self._machine(m)
        self._memory(m)
        self._storage(m)
        self._disk(m)
        self._cpu(m)
        self._gpu(m)
        self._startup(m)
        self._background(m)
        self._power(m)
        self._drivers(m)
        self._updates(m)
        self._network(m)
        self._stability(m)
        self._security(m)
        return m

    def _machine(self, m: dict):
        m["machine"] = ""
        m["os"] = "macOS"
        m["os_build"] = ""
        m["board_name"] = ""
        m["cpu_socket"] = ""
        m["bios_age_days"] = None
        m["is_laptop"] = True  # Apple only makes laptops + desktops; check battery

        sw_vers = _run_json(["sw_vers", "-json"])
        if isinstance(sw_vers, dict):
            m["os"] = f"macOS {sw_vers.get('ProductVersion', '')}"
            m["os_build"] = sw_vers.get("BuildVersion", "")

        # Hardware model
        sp_hw = _run(["system_profiler", "SPHardwareDataType", "-json"])
        if sp_hw:
            try:
                d = json.loads(sp_hw)
                hw = d.get("SPHardwareDataType", [{}])[0]
                m["machine"] = hw.get("machine_model", "")
            except Exception:
                pass

        # Board info — dmidecode doesn't exist, use sysctl
        model = _run(["sysctl", "-n", "hw.model"]).strip()
        m["board_name"] = model

        # Battery = laptop heuristic
        try:
            _run(["pmset", "-g", "batt"])
            m["is_laptop"] = True
        except Exception:
            m["is_laptop"] = False

    # ---- Memory ----
    def _memory(self, m: dict):
        vm = psutil.virtual_memory()
        m["ram_total_gb"] = round(vm.total / 1024**3, 1)
        m["ram_used_pct"] = vm.percent
        m["commit_used_pct"] = round(
            (vm.used + psutil.swap_memory().used) / (vm.total + psutil.swap_memory().total) * 100, 0
        ) if (vm.total + psutil.swap_memory().total) else 0

        procs = sorted(psutil.process_iter(["name", "memory_info"]),
                       key=lambda p: p.info["memory_info"].rss or 0, reverse=True)[:5]
        m["top_mem"] = ", ".join(
            f"{p.info['name']} ({round((p.info['memory_info'].rss or 0) / 1024**3, 1)} GB)"
            for p in procs
        )
        m["top_mem_gb"] = round((procs[0].info["memory_info"].rss or 0) / 1024**3, 1) if procs else 0

        m["ram_slots_used"] = 1
        m["ram_slots_total"] = 1
        m["ram_type"] = "Unified"
        m["ram_form"] = "laptop" if m.get("is_laptop") else "desktop"

        # Memory type from sysctl
        memtype_map = {
            "0x1": "Other", "0x7": "DRAM", "0xc": "DDR", "0x12": "DDR2",
            "0x18": "DDR2 FB-DIMM", "0x13": "DDR2 FB-DIMM", "0x14": "DDR2",
            "0x18": "DDR3", "0x1A": "DDR4", "0x22": "LPDDR4",
        }
        # Apple Silicon = unified = LPDDR4X/5; modern Intel = DDR4/DDR5
        sp_mem = _run(["system_profiler", "SPMemoryDataType", "-json"])
        if sp_mem:
            try:
                d = json.loads(sp_mem)
                items = d.get("SPMemoryDataType", [{}])
                if items:
                    ctype = items[0].get("dimm_comp_type", "")
                    m["ram_type"] = ctype or "Unified"
                    m["ram_slots_total"] = len(
                        [item for item in items if item.get("dimm_size")]
                    )
                    m["ram_slots_used"] = m["ram_slots_total"]
            except Exception:
                pass

    # ---- Storage ----
    def _storage(self, m: dict):
        df = _run(["df", "-h", "/"])
        m["sys_size_gb"] = 0
        m["sys_free_gb"] = 0
        m["sys_free_pct"] = 100
        for line in df.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 5:
                size_str = parts[1]
                avail_str = parts[3]
                pct_str = parts[4].rstrip("%")
                m["sys_size_gb"] = self._parse_size_gb(size_str)
                m["sys_free_gb"] = self._parse_size_gb(avail_str)
                try:
                    m["sys_free_pct"] = round(int((m["sys_size_gb"] - m["sys_free_gb"]) / m["sys_size_gb"] * 100), 0)
                except (ZeroDivisionError, TypeError):
                    pass
                break

        # Temp files
        temp_dirs = ["/tmp", os.path.expandvars("$TMPDIR")]
        tb = sum(_folder_gb(d, 2) for d in temp_dirs if d)
        m["temp_gb"] = round(tb, 2)
        m["recycle_gb"] = 0.0

    def _parse_size_gb(self, s: str) -> float:
        s = s.strip().upper()
        if s.endswith("G"):
            return float(s[:-1])
        if s.endswith("GB"):
            return float(s[:-2])
        if s.endswith("T"):
            return float(s[:-1]) * 1024
        if s.endswith("TB"):
            return float(s[:-2]) * 1024
        if s.endswith("M"):
            return float(s[:-1]) / 1024
        return float(s) / (1024**3)

    # ---- Disk Speed/Health ----
    def _disk(self, m: dict):
        m["sys_is_hdd"] = False
        m["secondary_hdds"] = []
        m["has_ssd"] = True  # All modern Macs use SSD
        m["disk_health_bad"] = []
        m["disk_busy_pct"] = 0
        m["trim_disabled"] = False

        # diskutil for info
        du = _run(["diskutil", "list", "-plist"])
        if du:
            try:
                import plistlib
                plist = plistlib.loads(du.encode() if isinstance(du, str) else du)
                for disk in plist.get("AllDisksAndPartitions", []):
                    media = disk.get("Content", "").lower()
                    if "apfs" in media or "ssd" in media:
                        m["has_ssd"] = True
            except Exception:
                pass

        # SMART
        smart = _run(["diskutil", "info", "/"])
        if "Solid State" in smart:
            m["has_ssd"] = True
        elif "Rotational" in smart:
            m["sys_is_hdd"] = True

        # TRIM
        trim = _run(["system_profiler", "SPNVMeDataType", "-json"])
        if "TRIM" in trim and "Disabled" in trim:
            m["trim_disabled"] = True

        # iostat for disk busy
        iostat = _run(["iostat", "-w", "1", "-n", "1"])
        for line in iostat.splitlines():
            if "disk0" in line or "disk1" in line:
                parts = line.split()
                try:
                    busy = float(parts[-1])  # % utilization
                    m["disk_busy_pct"] = int(min(100, busy))
                except (IndexError, ValueError):
                    pass
                break

    # ---- CPU ----
    def _cpu(self, m: dict):
        m["cpu_name"] = ""
        m["cpu_token"] = ""
        m["cpu_rank"] = 0
        m["cpu_rank_name"] = ""
        m["cpu_upgrade"] = {}
        m["cpu_cores"] = psutil.cpu_count(logical=False) or 0
        m["cpu_threads"] = psutil.cpu_count(logical=True) or 0

        freq = psutil.cpu_freq()
        m["cpu_max_mhz"] = int(freq.max) if freq and freq.max else 0
        m["cpu_current_mhz"] = int(freq.current) if freq and freq.current else 0
        m["cpu_load_pct"] = int(psutil.cpu_percent(interval=0.1))
        m["cpu_clock_pct"] = (
            round(m["cpu_current_mhz"] / m["cpu_max_mhz"] * 100, 0)
            if m["cpu_max_mhz"] > 0 and m["cpu_current_mhz"] > 0 else 0
        )

        # CPU name from sysctl
        sp_cpu = _run(["sysctl", "-n", "machdep.cpu.brand_string"]).strip()
        if sp_cpu:
            m["cpu_name"] = sp_cpu

        # Apple Silicon detection
        cpu_brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"]).strip()
        if "Apple" in cpu_brand or "M1" in cpu_brand or "M2" in cpu_brand or "M3" in cpu_brand:
            m["cpu_name"] = cpu_brand or "Apple Silicon"
            m["cpu_socket"] = "BGA (soldered)"

        procs = sorted(psutil.process_iter(["name", "cpu_times"]),
                       key=lambda p: (p.info["cpu_times"].user + p.info["cpu_times"].system)
                       if p.info["cpu_times"] else 0, reverse=True)[:3]
        m["top_cpu"] = ", ".join(sorted(set(p.info["name"] for p in procs if p.info["name"])))

        m["uptime_days"] = round((datetime.now().timestamp() - psutil.boot_time()) / 86400, 1)

        # CPU rank for Apple Silicon
        if "Apple" in m["cpu_name"]:
            # Apple Silicon approximate tiers
            apple_ranks = {
                "M4 Max": 980, "M4 Pro": 900, "M4": 840,
                "M3 Max": 920, "M3 Pro": 830, "M3": 750,
                "M2 Ultra": 950, "M2 Max": 870, "M2 Pro": 780, "M2": 700,
                "M1 Ultra": 840, "M1 Max": 800, "M1 Pro": 720, "M1": 650,
            }
            for chip, rank in apple_ranks.items():
                if chip in m["cpu_name"]:
                    m["cpu_rank"] = rank
                    m["cpu_rank_name"] = chip
                    break

        # All Mac CPUs are soldered
        m["cpu_upgrade"] = {
            "can_buy": False,
            "text": "CPU is soldered (Apple Silicon / BGA) - not upgradable",
            "query": "",
            "note": "All modern Macs use soldered CPUs. Focus on RAM, storage, and GPU (eGPU over Thunderbolt if supported).",
            "confidence": "Apple soldered CPU",
            "recommended": "",
            "rank": 0,
            "support_url": "",
        }

    # ---- GPU ----
    def _gpu(self, m: dict):
        m["gpus"] = []
        m["gpu_details"] = []
        m["has_dedicated_gpu"] = False
        m["vram_gb"] = 0
        m["gpu_driver_age_days"] = 0
        m["gpu_problem_count"] = 0
        m["gpu_rank"] = 0

        sp_disp = _run(["system_profiler", "SPDisplaysDataType", "-json"])
        if sp_disp:
            try:
                d = json.loads(sp_disp)
                displays = d.get("SPDisplaysDataType", [{}])
                if displays:
                    disp = displays[0]
                    name = disp.get("spserial_display_primary", "") or disp.get("_name", "")
                    if not name:
                        name = disp.get("spdisplays_vendor", "") + " " + disp.get("spdisplays_model", "")
                    m["gpus"].append(name)

                    # Apple Silicon: unified memory
                    mem_shared = disp.get("spdisplays_mtlmegabytes", "0")
                    if mem_shared:
                        m["vram_gb"] = round(int(mem_shared) / 1024**2 / 1024, 1)
                        m["has_dedicated_gpu"] = bool(disp.get("spdisplays_vendor", "").lower() != "apple")

                    if "Apple" in name or not m["has_dedicated_gpu"]:
                        m["has_dedicated_gpu"] = False
                        # Total system RAM is effectively unified VRAM for Apple Silicon
                        m["vram_gb"] = max(m["vram_gb"], m.get("ram_total_gb", 0))

                    m["gpu_details"].append({
                        "name": name, "dedicated": m["has_dedicated_gpu"],
                        "vram_gb": m["vram_gb"],
                        "driver_version": "", "driver_age_days": 0,
                    })
            except Exception:
                pass

        if m["gpus"]:
            from catalogs.gpus import find as find_gpu
            for gname in m["gpus"]:
                entry = find_gpu(gname)
                if entry and entry.rank > m["gpu_rank"]:
                    m["gpu_rank"] = entry.rank

    # ---- Startup ----
    def _startup(self, m: dict):
        items = []

        # launchctl list
        launch = _run(["launchctl", "list"])
        for line in launch.strip().splitlines()[1:]:  # skip header
            parts = line.split()
            if parts and not parts[0].startswith("-"):
                items.append(parts[-1])

        # User launch agents
        agents = os.path.expanduser("~/Library/LaunchAgents")
        if os.path.isdir(agents):
            for f in os.listdir(agents):
                if f.endswith(".plist"):
                    items.append(f.replace(".plist", ""))

        m["startup_count"] = len(items)
        m["startup_names"] = ", ".join(items[:12])

    # ---- Background ----
    def _background(self, m: dict):
        svc_items = []

        # launchd agents (user)
        for agent_dir in [
            os.path.expanduser("~/Library/LaunchAgents"),
            "/Library/LaunchAgents",
            "/Library/LaunchDaemons",
            "/System/Library/LaunchAgents",
            "/System/Library/LaunchDaemons",
        ]:
            if os.path.isdir(agent_dir):
                try:
                    for f in os.listdir(agent_dir):
                        if f.endswith(".plist"):
                            svc_items.append(f.replace(".plist", ""))
                except (OSError, PermissionError):
                    pass

        m["third_party_service_count"] = max(5, len(svc_items))
        m["third_party_service_names"] = ", ".join(svc_items[:12])

        # Cron
        task_items = []
        crontab = _run(["crontab", "-l"])
        for line in crontab.splitlines():
            if line.strip() and not line.startswith("#"):
                task_items.append(line.split()[-1].split("/")[-1])
        m["scheduled_task_count"] = max(3, len(task_items))
        m["scheduled_task_names"] = ", ".join(task_items[:12])

    # ---- Power ----
    def _power(self, m: dict):
        m["power_plan"] = "macOS"
        m["power_saver"] = False
        m["on_battery"] = False
        m["battery_present"] = False
        m["thermal_temp_c"] = 0

        bat = _try(lambda: psutil.sensors_battery(), None)
        if bat:
            m["battery_present"] = True
            m["on_battery"] = not bat.power_plugged

        # Thermal
        if m["battery_present"]:
            pmset = _run(["pmset", "-g", "therm"])
            for line in pmset.splitlines():
                m_temp = re.search(r"CPU\s+temperature[:\s]+([\d.]+)", line, re.IGNORECASE)
                if m_temp:
                    m["thermal_temp_c"] = round(float(m_temp.group(1)), 1)
                    break

        # Power profile
        try:
            pmset = _run(["pmset", "-g", "custom"])
            if "powermode" in pmset.lower():
                m["power_plan"] = pmset.strip()
        except Exception:
            pass

    # ---- Drivers ----
    def _drivers(self, m: dict):
        m["problem_device_count"] = 0
        m["problem_device_names"] = ""
        m["old_driver_count"] = 0
        m["old_driver_names"] = ""

        # kextstat for kernel extensions
        kextstat = _run(["kextstat"])
        bad_kexts = []
        for line in kextstat.splitlines()[1:]:
            if "com.apple" not in line and line.strip():
                parts = line.split()
                if len(parts) >= 6:
                    # check for error in refs
                    refs = parts[4]
                    if re.search(r"\d+", refs):
                        bad_kexts.append(" ".join(parts[5:6]))

        m["problem_device_count"] = len(bad_kexts[:10])
        m["problem_device_names"] = ", ".join(bad_kexts[:8])

    # ---- Updates ----
    def _updates(self, m: dict):
        m["last_update_days"] = None
        m["reboot_pending"] = False
        m["update_services_stopped"] = []

        # softwareupdate last check
        su = _run(["softwareupdate", "-l"])
        # Check last check date from log
        log = _run(["log", "show", "--predicate", 'eventMessage contains "softwareupdate"',
                    "--last", "7d", "--style", "compact", "-n", "1"])
        if log:
            m["last_update_days"] = 0

        if m["last_update_days"] is None:
            # check installer receipts
            receipts = "/var/db/receipts/"
            if os.path.isdir(receipts):
                latest = 0
                for f in os.listdir(receipts):
                    if "InstallHistory" in f or f.endswith(".plist"):
                        continue
                    fp = os.path.join(receipts, f)
                    mtime = _try(lambda: os.path.getmtime(fp), 0)
                    if mtime and mtime > latest:
                        latest = mtime
                if latest:
                    m["last_update_days"] = int((datetime.now().timestamp() - latest) / 86400)

        # Reboot pending: check if softwareupdate needs restart
        reboot_file = "/var/db/.AppleSetupDone"
        m["reboot_pending"] = os.path.exists("/.RestartAction") or os.path.exists("/var/run/reboot-required")

    # ---- Network / Browser ----
    def _network(self, m: dict):
        m["net_link_mbps"] = 0
        m["network_names"] = ""
        m["wifi_signal_pct"] = 0

        if_addrs = psutil.net_if_addrs()
        if_stats = psutil.net_if_stats()
        max_link = 0
        names = []
        for name, snics in if_addrs.items():
            if name in if_stats and if_stats[name].isup:
                speed = if_stats[name].speed
                if speed > 0:
                    max_link = max(max_link, speed)
                names.append(name)

        m["net_link_mbps"] = max_link
        m["network_names"] = ", ".join(names[:5])

        # WiFi from networksetup
        airport = _run(["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"])
        for line in airport.splitlines():
            if "agrCtlRSSI" in line:
                m_sig = re.search(r"(-\d+)", line)
                if m_sig:
                    dbm = int(m_sig.group(1))
                    m["wifi_signal_pct"] = max(0, min(100, round((dbm + 100) * 2)))

        # Browsers
        self._scan_browsers(m)

    def _scan_browsers(self, m: dict):
        m["browser_ext_count"] = 0
        m["browser_cache_gb"] = 0.0

        profiles_dirs = [
            os.path.expandvars("$HOME/Library/Application Support/Google/Chrome"),
            os.path.expandvars("$HOME/Library/Application Support/Microsoft Edge"),
            os.path.expandvars("$HOME/Library/Application Support/BraveSoftware/Brave-Browser"),
            os.path.expandvars("$HOME/Library/Application Support/Vivaldi"),
            os.path.expandvars("$HOME/Library/Application Support/Opera"),
            os.path.expandvars("$HOME/Library/Application Support/Firefox/Profiles"),
        ]
        for root in profiles_dirs:
            if not os.path.isdir(root):
                continue
            for pdir in os.listdir(root):
                p0 = os.path.join(root, pdir)
                if not os.path.isdir(p0):
                    continue
                if "Firefox" in root:
                    p0 = pdir  # firefox dirs are already profile dirs
                ext_path = os.path.join(p0, "Extensions")
                if os.path.isdir(ext_path):
                    try:
                        m["browser_ext_count"] += len(os.listdir(ext_path))
                    except OSError:
                        pass
                for cn in ("Cache", "Code Cache", "GPUCache"):
                    m["browser_cache_gb"] += _folder_gb(os.path.join(p0, cn), 2)

                # Firefox extensions.json
                ff_meta = os.path.join(p0, "extensions.json")
                if os.path.isfile(ff_meta):
                    try:
                        with open(ff_meta) as fh:
                            data = json.load(fh)
                        m["browser_ext_count"] += sum(
                            1 for a in data.get("addons", []) if a.get("active")
                        )
                    except (OSError, json.JSONDecodeError):
                        pass

        m["browser_cache_gb"] = round(m["browser_cache_gb"], 2)

    # ---- Stability ----
    def _stability(self, m: dict):
        m["system_error_count"] = 0
        m["disk_event_count"] = 0
        m["whea_event_count"] = 0
        m["bug_check_count"] = 0
        m["app_crash_count"] = 0

        # Use unified log for panic/kernel panics
        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        panic = _run([
            "log", "show",
            "--predicate", 'eventMessage contains "panic" or eventMessage contains "kernel"',
            "--last", "7d", "-n", "50"
        ])
        m["bug_check_count"] = panic.count("panic")

        # App crashes from crash reporter
        crash_dir = os.path.expanduser("~/Library/Logs/DiagnosticReports")
        if os.path.isdir(crash_dir):
            cutoff = datetime.now() - timedelta(days=7)
            crash_count = 0
            for f in os.listdir(crash_dir):
                if f.endswith(".ips") or f.endswith(".crash"):
                    fp = os.path.join(crash_dir, f)
                    mt = _try(lambda: os.path.getmtime(fp), 0)
                    if mt and datetime.fromtimestamp(mt) > cutoff:
                        crash_count += 1
            m["app_crash_count"] = crash_count

    # ---- Security ----
    def _security(self, m: dict):
        m["av_enabled"] = True  # XProtect always on
        m["realtime_protection"] = True
        m["defs_age_days"] = 0
        m["suspicious_count"] = 0
        m["suspicious_list"] = []
        m["hosts_custom_entries"] = 0

        # XProtect version
        xprotect = _run(["system_profiler", "SPXProtectDataType", "-json"])
        if xprotect:
            m["av_enabled"] = True

        # Suspicious files
        exe_ext = re.compile(r"\.(dmg|pkg|app|command|sh|py|rb)$", re.IGNORECASE)
        double_ext = re.compile(
            r"\.(?:pdf|doc|docx|xls|xlsx|jpg|png|zip|rar|txt|csv|htm|html)"
            r"\.(?:command|sh|py|rb|app|dmg|pkg)$",
            re.IGNORECASE,
        )

        sus = []
        for d in [
            os.path.expanduser("~/Downloads"),
            "/tmp",
        ]:
            if not os.path.isdir(d):
                continue
            try:
                for f in os.listdir(d)[:100]:
                    fp = os.path.join(d, f)
                    if not os.path.isfile(fp):
                        continue
                    if not exe_ext.search(f):
                        continue
                    if double_ext.search(f):
                        sus.append(f"{fp} [disguised double extension]")
            except (OSError, PermissionError):
                pass

        m["suspicious_count"] = len(sus)
        m["suspicious_list"] = sus[:12]

        # Gatekeeper status
        gk = _run(["spctl", "--status"])
        m["gatekeeper_enabled"] = "enabled" in gk.lower() if gk else False


def _folder_gb(path: str, depth: int = 2) -> float:
    if not path or not os.path.isdir(path):
        return 0.0
    total = 0
    for root, dirs, files in os.walk(path):
        level = root.replace(path, "").count(os.sep)
        if level > depth:
            dirs[:] = []
            continue
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return round(total / 1024**3, 2)
