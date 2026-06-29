"""macOS metric collector."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timedelta

import psutil

from platforms.base import MetricCollector
from platforms.common import average_cpu_load, folder_size_gb, process_snapshot, run_command


def _run(cmd: list[str], timeout: int = 10) -> str:
    result = run_command(cmd, timeout)
    return result.stdout if result.ok else ""


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
    def collect(self, progress_callback=None) -> dict:
        return self._collect_steps([
            ("system", "Reading machine details", self._machine),
            ("memory", "Checking memory", self._memory),
            ("storage", "Checking storage space", self._storage),
            ("diskspeed", "Checking disk type and health", self._disk),
            ("gpu", "Checking graphics", self._gpu),
            ("cpu", "Checking processor performance", self._cpu),
            ("startup", "Checking login items", self._startup),
            ("background", "Checking launch agents", self._background),
            ("power", "Checking power and battery", self._power),
            ("drivers", "Checking hardware warnings", self._drivers),
            ("updates", "Checking update state", self._updates),
            ("network", "Checking network and browsers", self._network),
            ("stability", "Checking recent crash reports", self._stability),
            ("security", "Checking macOS security controls", self._security),
        ], progress_callback)

    def _machine(self, m: dict):
        m["machine"] = ""
        m["os"] = "macOS"
        m["os_build"] = ""
        m["board_name"] = ""
        m["cpu_socket"] = ""
        m["bios_age_days"] = None
        m["is_laptop"] = False
        m["apple_silicon"] = False
        m["platform"] = "macOS"

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
                m["machine"] = hw.get("machine_model", "") or hw.get("machine_name", "")
                chip = hw.get("chip_type", "")
                if chip:
                    m["cpu_name"] = chip
                    m["apple_silicon"] = chip.lower().startswith("apple")
            except Exception:
                pass

        # Board info — dmidecode doesn't exist, use sysctl
        model = _run(["sysctl", "-n", "hw.model"]).strip()
        m["board_name"] = model

        # Battery = laptop heuristic
        battery_output = _run(["pmset", "-g", "batt"])
        m["is_laptop"] = "InternalBattery" in battery_output

    # ---- Memory ----
    def _memory(self, m: dict):
        vm = psutil.virtual_memory()
        m["ram_total_gb"] = round(vm.total / 1024**3, 1)
        m["ram_used_pct"] = vm.percent
        m["commit_used_pct"] = round(
            (vm.used + psutil.swap_memory().used) / (vm.total + psutil.swap_memory().total) * 100, 0
        ) if (vm.total + psutil.swap_memory().total) else 0

        cpu_rows, memory_rows = process_snapshot()
        m["top_cpu_rows"] = cpu_rows
        m["top_mem_rows"] = memory_rows
        m["top_mem"] = ", ".join(f"{name} ({value:.1f} GB)" for name, value in memory_rows)
        m["top_mem_gb"] = memory_rows[0][1] if memory_rows else 0

        m["ram_slots_used"] = 0
        m["ram_slots_total"] = 0
        m["ram_type"] = "Unified" if m.get("apple_silicon") else "RAM"
        m["ram_form"] = "laptop" if m.get("is_laptop") else "desktop"
        m["memory_upgradable"] = not m.get("apple_silicon", False)

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
                    m["ram_slots_total"] = len(items)
                    m["ram_slots_used"] = len([item for item in items if item.get("dimm_size")])
            except Exception:
                pass

    # ---- Storage ----
    def _storage(self, m: dict):
        usage = psutil.disk_usage("/")
        m["sys_size_gb"] = round(usage.total / 1024**3, 1)
        m["sys_free_gb"] = round(usage.free / 1024**3, 1)
        m["sys_free_pct"] = round(usage.free / usage.total * 100) if usage.total else 0

        # Temp files
        temp_dirs = ["/tmp", os.path.expandvars("$TMPDIR")]
        tb = sum(_folder_gb(d, 2) for d in temp_dirs if d)
        m["temp_gb"] = round(tb, 2)
        m["recycle_gb"] = _folder_gb(os.path.expanduser("~/.Trash"), 2)

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
        m["has_ssd"] = False
        m["disk_health_bad"] = []
        m["disk_busy_pct"] = None
        m["trim_disabled"] = False
        m["disk_type_known"] = False
        m["system_disk_type"] = "Unknown"
        m["disk_models"] = []
        m["storage_upgradable"] = not m.get("apple_silicon", False)

        # diskutil for info
        du = _run(["diskutil", "list", "-plist"])
        if du:
            try:
                import plistlib
                plist = plistlib.loads(du.encode() if isinstance(du, str) else du)
                for disk in plist.get("AllDisksAndPartitions", []):
                    media = disk.get("Content", "").lower()
                    if "ssd" in media:
                        m["has_ssd"] = True
            except Exception:
                pass

        # SMART
        smart = _run(["diskutil", "info", "/"])
        solid_state = re.search(r"Solid State:\s*(Yes|No)", smart, re.IGNORECASE)
        if solid_state and solid_state.group(1).lower() == "yes":
            m["has_ssd"] = True
            m["disk_type_known"] = True
            m["system_disk_type"] = "SSD/NVMe"
        elif (solid_state and solid_state.group(1).lower() == "no") or "Rotational" in smart:
            m["sys_is_hdd"] = True
            m["disk_type_known"] = True
            m["system_disk_type"] = "HDD"
        model_match = re.search(r"Device / Media Name:\s*(.+)", smart)
        if model_match:
            m["disk_models"].append(model_match.group(1).strip())
        smart_match = re.search(r"SMART Status:\s*(.+)", smart)
        if smart_match and smart_match.group(1).strip().lower() not in ("verified", "not supported"):
            m["disk_health_bad"].append(smart_match.group(1).strip())

        # TRIM
        trim = _run(["system_profiler", "SPNVMeDataType", "-json"])
        if "TRIM" in trim and "Disabled" in trim:
            m["trim_disabled"] = True

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
        m["cpu_load_pct"] = average_cpu_load()
        m["cpu_clock_pct"] = (
            round(m["cpu_current_mhz"] / m["cpu_max_mhz"] * 100, 0)
            if m["cpu_max_mhz"] > 0 and m["cpu_current_mhz"] > 0 else 0
        )

        # CPU name from sysctl
        sp_cpu = m.get("cpu_name") or _run(["sysctl", "-n", "machdep.cpu.brand_string"]).strip()
        if sp_cpu:
            m["cpu_name"] = sp_cpu

        # Apple Silicon detection
        cpu_brand = sp_cpu
        if m.get("apple_silicon") or re.search(r"\bM[1-9]", cpu_brand):
            m["cpu_name"] = cpu_brand or "Apple Silicon"
            m["cpu_socket"] = "BGA (soldered)"

        cpu_rows = m.get("top_cpu_rows") or process_snapshot()[0]
        m["top_cpu"] = ", ".join(f"{name} ({value:.0f}%)" for name, value in cpu_rows)

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
            "note": "Mac CPUs are not field-upgradable. Apple Silicon also has fixed unified memory and internal storage; Intel Mac capabilities vary by exact model.",
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
                    name = disp.get("sppci_model", "") or disp.get("_name", "")
                    if not name:
                        name = disp.get("spdisplays_vendor", "") + " " + disp.get("spdisplays_model", "")
                    m["gpus"].append(name)

                    # Apple Silicon: unified memory
                    vram_text = str(disp.get("spdisplays_vram", "") or disp.get("spdisplays_vram_shared", ""))
                    vram_match = re.search(r"([\d.]+)\s*(GB|MB)", vram_text, re.IGNORECASE)
                    if vram_match:
                        value = float(vram_match.group(1))
                        m["vram_gb"] = round(value if vram_match.group(2).upper() == "GB" else value / 1024, 1)
                    vendor = str(disp.get("spdisplays_vendor", ""))
                    m["has_dedicated_gpu"] = bool(re.search(r"AMD|NVIDIA", vendor + " " + name, re.IGNORECASE))

                    if m.get("apple_silicon"):
                        m["has_dedicated_gpu"] = False
                        m["vram_gb"] = 0

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
        for line in launch.strip().splitlines()[1:]:
            parts = line.split()
            if parts and not parts[-1].startswith("com.apple."):
                items.append(parts[-1])

        # User launch agents
        agents = os.path.expanduser("~/Library/LaunchAgents")
        if os.path.isdir(agents):
            for f in os.listdir(agents):
                if f.endswith(".plist"):
                    items.append(f.replace(".plist", ""))

        items = sorted(set(items))
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
        ]:
            if os.path.isdir(agent_dir):
                try:
                    for f in os.listdir(agent_dir):
                        if f.endswith(".plist"):
                            svc_items.append(f.replace(".plist", ""))
                except (OSError, PermissionError):
                    pass

        svc_items = sorted(set(svc_items))
        m["third_party_service_count"] = len(svc_items)
        m["third_party_service_names"] = ", ".join(svc_items[:12])

        # Cron
        task_items = []
        crontab = _run(["crontab", "-l"])
        for line in crontab.splitlines():
            if line.strip() and not line.startswith("#"):
                task_items.append(line.split()[-1].split("/")[-1])
        m["scheduled_task_count"] = len(task_items)
        m["scheduled_task_names"] = ", ".join(task_items[:12])

    # ---- Power ----
    def _power(self, m: dict):
        m["power_plan"] = "macOS"
        m["power_saver"] = False
        m["on_battery"] = False
        m["battery_present"] = False
        m["battery_health_pct"] = None
        m["thermal_temp_c"] = 0

        bat = _try(lambda: psutil.sensors_battery(), None)
        if bat:
            m["battery_present"] = True
            m["on_battery"] = not bat.power_plugged

        power_json = _run_json(["system_profiler", "SPPowerDataType", "-json"])
        if isinstance(power_json, dict):
            payload = str(power_json)
            maximum = re.search(r"maximum_capacity[^0-9]*(\d+)", payload, re.IGNORECASE)
            if maximum:
                m["battery_health_pct"] = int(maximum.group(1))

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
            low_power = bool(re.search(r"lowpowermode\s+1", pmset, re.IGNORECASE))
            m["power_saver"] = low_power
            m["power_plan"] = "Low Power Mode" if low_power else "Automatic"
        except Exception:
            pass

    # ---- Drivers ----
    def _drivers(self, m: dict):
        m["problem_device_count"] = 0
        m["problem_device_names"] = ""
        m["old_driver_count"] = 0
        m["old_driver_names"] = ""

        disabled = _run_json(["system_profiler", "SPDisabledSoftwareDataType", "-json"])
        items = disabled.get("SPDisabledSoftwareDataType", []) if isinstance(disabled, dict) else []
        warnings = [str(item.get("_name", "Disabled system extension")) for item in items if isinstance(item, dict)]
        m["problem_device_count"] = len(warnings)
        m["problem_device_names"] = ", ".join(warnings[:8])
        if not disabled:
            self.set_confidence(m, "drivers", "Low")

    # ---- Updates ----
    def _updates(self, m: dict):
        m["last_update_days"] = None
        m["reboot_pending"] = False
        m["update_services_stopped"] = []

        try:
            import plistlib
            with open("/Library/Receipts/InstallHistory.plist", "rb") as history_file:
                history = plistlib.load(history_file)
            dates = [
                item.get("date") for item in history
                if isinstance(item, dict)
                and item.get("date")
                and re.search(r"macOS|Security Update|Rapid Security", str(item.get("displayName", "")), re.IGNORECASE)
            ]
            if dates:
                latest = max(dates)
                m["last_update_days"] = max(0, (datetime.now(latest.tzinfo) - latest).days)
        except (OSError, ValueError, TypeError):
            self.set_confidence(m, "updates", "Low")

        # Reboot pending: check if softwareupdate needs restart
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

        cutoff = datetime.now() - timedelta(days=7)
        for crash_dir in (os.path.expanduser("~/Library/Logs/DiagnosticReports"), "/Library/Logs/DiagnosticReports"):
            if not os.path.isdir(crash_dir):
                continue
            for filename in os.listdir(crash_dir):
                path = os.path.join(crash_dir, filename)
                modified = _try(lambda: os.path.getmtime(path), 0)
                if not modified or datetime.fromtimestamp(modified) <= cutoff:
                    continue
                if filename.endswith(".panic") or "panic" in filename.lower():
                    m["bug_check_count"] += 1
                elif filename.endswith((".ips", ".crash")):
                    m["app_crash_count"] += 1

    # ---- Security ----
    def _security(self, m: dict):
        m["av_enabled"] = None
        m["realtime_protection"] = None
        m["defs_age_days"] = None
        m["suspicious_count"] = 0
        m["suspicious_list"] = []
        m["hosts_custom_entries"] = 0
        m["firewall_enabled"] = None

        # XProtect version
        xprotect = _run(["system_profiler", "SPXProtectDataType", "-json"])
        if xprotect:
            m["av_enabled"] = True
            m["realtime_protection"] = True

        sus = []
        for d in [os.path.expanduser("~/Library/LaunchAgents")]:
            if not os.path.isdir(d):
                continue
            try:
                for f in os.listdir(d)[:100]:
                    fp = os.path.join(d, f)
                    if not os.path.isfile(fp):
                        continue
                    if f.lower().endswith((".command", ".sh", ".py", ".rb")):
                        sus.append(f"{f} [script configured in a startup location]")
            except (OSError, PermissionError):
                pass

        m["suspicious_count"] = len(sus)
        m["suspicious_list"] = sus[:12]

        # Gatekeeper status
        gk = _run(["spctl", "--status"])
        m["gatekeeper_enabled"] = "enabled" in gk.lower() if gk else None
        firewall = _run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"])
        if firewall:
            m["firewall_enabled"] = "enabled" in firewall.lower()


def _folder_gb(path: str, depth: int = 2) -> float:
    return folder_size_gb(path, depth)
