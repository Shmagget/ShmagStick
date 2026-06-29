"""Windows metric collector — ported from ShmagStick.ps1 Collect-Metrics."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import psutil

from platforms.base import MetricCollector


def _try(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _cim_date_to_dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        # WMI datetime: yyyymmddHHMMSS.mmmmmm+UUU
        s = str(value)
        if len(s) >= 14:
            return datetime.strptime(s[:14], "%Y%m%d%H%M%S")
    except Exception:
        pass
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _age_days(value) -> int | None:
    d = _cim_date_to_dt(value)
    if not d:
        return None
    return max(0, (datetime.now() - d).days)


def _normalize_hw(value: str) -> str:
    v = value.upper()
    v = re.sub(r"\(R\)|\(TM\)|CPU|PROCESSOR|GRAPHICS|GEFORCE|RADEON|AMD|INTEL|NVIDIA|@.*$", " ", v)
    v = re.sub(r"[^A-Z0-9]+", " ", v)
    return v.strip()


def _folder_gb(path: str, depth: int = 2) -> float:
    if not path or not os.path.isdir(path):
        return 0.0
    total = 0
    try:
        for root, dirs, files in os.walk(path):
            level = root.replace(path, "").count(os.sep)
            if level > depth:
                dirs[:] = []
                continue
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    except Exception:
        pass
    return round(total / (1024 ** 3), 2)


def _link_speed_mbps(bits) -> int:
    if not bits:
        return 0
    return int(round(float(bits) / 1_000_000))


class WindowsCollector(MetricCollector):
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

    # ---- Machine / Board / BIOS ----
    def _machine(self, m: dict):
        os_info = _try(lambda: psutil.os.name, "Windows")
        m["machine"] = ""
        m["os"] = ""
        m["os_build"] = ""
        m["board_name"] = ""
        m["cpu_socket"] = ""
        m["bios_age_days"] = None
        m["is_laptop"] = False

        # Use ctypes for OS version (more reliable than wmi on some systems)
        try:
            import ctypes
            ver = sys.getwindowsversion()
            m["os_build"] = str(ver.build)
        except Exception:
            pass

        # Try WMI via subprocess / powershell for board info
        self._wmi_query("Win32_OperatingSystem", [
            "Caption", "BuildNumber", "CSDVersion"
        ], lambda row: (
            m.update({"os": row.get("Caption", ""), "os_build": row.get("BuildNumber", "")})
        ))

        self._wmi_query("Win32_ComputerSystem", [
            "Manufacturer", "Model", "TotalPhysicalMemory", "PCSystemType"
        ], lambda row: (
            m.update({
                "machine": f"{row.get('Manufacturer', '')} {row.get('Model', '')}".strip(),
                "is_laptop": str(row.get("PCSystemType", "3")) == "2",
            })
        ))

        self._wmi_query("Win32_BaseBoard", [
            "Manufacturer", "Product"
        ], lambda row: (
            m.update({
                "board_name": f"{row.get('Manufacturer', '')} {row.get('Product', '')}".strip(),
            })
        ))

        m["board_name"] = m.get("board_name", "")

        self._wmi_query("Win32_BIOS", ["ReleaseDate"], lambda row: (
            m.update({"bios_age_days": _age_days(row.get("ReleaseDate"))})
        ))

    # ---- Memory ----
    def _memory(self, m: dict):
        vm = psutil.virtual_memory()
        m["ram_total_gb"] = round(vm.total / (1024 ** 3), 1)
        m["ram_used_pct"] = vm.percent
        total_virt = vm.total + psutil.swap_memory().total
        used_virt = vm.used + psutil.swap_memory().used
        m["commit_used_pct"] = round(used_virt / total_virt * 100, 0) if total_virt else 0

        # Top memory users
        procs = sorted(psutil.process_iter(["name", "memory_info"]),
                       key=lambda p: p.info["memory_info"].rss or 0, reverse=True)[:5]
        m["top_mem"] = ", ".join(
            f"{p.info['name']} ({round((p.info['memory_info'].rss or 0) / (1024**3), 1)} GB)"
            for p in procs
        )
        m["top_mem_gb"] = round((procs[0].info["memory_info"].rss or 0) / (1024**3), 1) if procs else 0

        # RAM slots
        m["ram_slots_used"] = 0
        m["ram_slots_total"] = 0
        try:
            import wmi
            c = wmi.WMI()
            dimm_count = 0
            for mem in c.Win32_PhysicalMemory():
                dimm_count += 1
            m["ram_slots_used"] = dimm_count
            for arr in c.Win32_PhysicalMemoryArray():
                m["ram_slots_total"] = arr.MemoryDevices
                break
        except Exception:
            pass

        # RAM type/form
        m["ram_type"] = "RAM"
        m["ram_form"] = "desktop"
        try:
            import wmi
            c = wmi.WMI()
            for pm in c.Win32_PhysicalMemory():
                smbios = int(pm.SMBIOSMemoryType or 0)
                type_map = {24: "DDR3", 26: "DDR4", 34: "DDR5", 35: "DDR5"}
                if smbios in type_map:
                    m["ram_type"] = type_map[smbios]
                if int(pm.FormFactor or 0) == 12:
                    m["ram_form"] = "laptop"
                break
        except Exception:
            pass

    # ---- Storage ----
    def _storage(self, m: dict):
        sys_drive = os.environ.get("SystemDrive", "C:")
        try:
            ld = psutil.disk_usage(sys_drive)
            m["sys_size_gb"] = round(ld.total / (1024 ** 3), 1)
            m["sys_free_gb"] = round(ld.free / (1024 ** 3), 1)
            m["sys_free_pct"] = round(ld.free / ld.total * 100, 0) if ld.total else 100
        except Exception:
            m["sys_size_gb"] = 0
            m["sys_free_gb"] = 0
            m["sys_free_pct"] = 100

        # Temp files
        env_temp = os.environ.get("TEMP", "")
        win_temp = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Temp")
        local_temp = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp")
        paths = list(dict.fromkeys([env_temp, win_temp, local_temp]))
        tb = sum(_folder_gb(p, 2) for p in paths if p)
        m["temp_gb"] = round(tb, 2)

        # Recycle Bin
        rb = 0
        for try_path in ["C:\\$Recycle.Bin"]:
            rb += _folder_gb(try_path, 1)
        m["recycle_gb"] = round(rb, 2)

    # ---- Disk Speed / Health ----
    def _disk(self, m: dict):
        m["sys_is_hdd"] = False
        m["secondary_hdds"] = []
        m["has_ssd"] = False
        m["disk_health_bad"] = []
        m["disk_busy_pct"] = 0
        m["trim_disabled"] = False

        # SSD vs HDD + SMART health via the Storage namespace (Windows 8+).
        # Win32_PhysicalDisk does NOT exist in root\cimv2 — the physical-disk
        # info with a real SSD/HDD MediaType lives in MSFT_PhysicalDisk.
        try:
            import wmi
            sys_letter = os.environ.get("SystemDrive", "C:").rstrip(":").upper()
            storage = wmi.WMI(namespace=r"root\Microsoft\Windows\Storage")

            # Map the system drive letter -> physical disk number.
            sys_disk_num = None
            try:
                for part in storage.MSFT_Partition():
                    dl = part.DriveLetter
                    letter = chr(dl) if isinstance(dl, int) and dl else str(dl or "")
                    if letter.upper() == sys_letter:
                        sys_disk_num = int(part.DiskNumber)
                        break
            except Exception:
                pass

            for pd in storage.MSFT_PhysicalDisk():
                media = int(pd.MediaType or 0)      # 3=HDD, 4=SSD, 5=SCM
                health = int(pd.HealthStatus or 0)  # 0=Healthy, 1=Warning, 2=Unhealthy
                name = pd.FriendlyName or "Disk"
                size_gb = round(int(pd.Size or 0) / (1024 ** 3)) if pd.Size else "?"
                if media == 4:
                    m["has_ssd"] = True
                if health != 0:
                    label = {1: "Warning", 2: "Unhealthy"}.get(health, "Unknown")
                    m["disk_health_bad"].append(f"{name} [{label}]")
                if media == 3:  # mechanical hard drive
                    try:
                        is_sys = (sys_disk_num is not None and int(pd.DeviceId) == sys_disk_num)
                    except (TypeError, ValueError):
                        is_sys = False
                    if is_sys:
                        m["sys_is_hdd"] = True
                    else:
                        m["secondary_hdds"].append(f"{name} ({size_gb} GB)")
        except Exception:
            pass

        # Disk busy
        try:
            import wmi
            c = wmi.WMI()
            for counter in c.Win32_PerfFormattedData_PerfDisk_PhysicalDisk():
                if counter.Name == "_Total":
                    m["disk_busy_pct"] = int(float(counter.PercentDiskTime or 0))
                    break
        except Exception:
            pass

        # TRIM
        try:
            r = subprocess.run(["fsutil", "behavior", "query", "DisableDeleteNotify"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and "= 1" in r.stdout:
                m["trim_disabled"] = True
        except Exception:
            pass

    # ---- CPU ----
    def _cpu(self, m: dict):
        cpu_info = _try(lambda: psutil.cpu_count(logical=False), 0) or 0
        threads = _try(lambda: psutil.cpu_count(logical=True), 0) or 0
        freq = _try(lambda: psutil.cpu_freq(), None)
        max_mhz = int(freq.max) if freq and freq.max else 0
        cur_mhz = int(freq.current) if freq and freq.current else 0
        load = _try(lambda: psutil.cpu_percent(interval=0.1), 0)
        clock_pct = round(cur_mhz / max_mhz * 100, 0) if max_mhz > 0 and cur_mhz > 0 else 0

        m["cpu_cores"] = cpu_info
        m["cpu_threads"] = threads
        m["cpu_max_mhz"] = max_mhz
        m["cpu_current_mhz"] = cur_mhz
        m["cpu_load_pct"] = int(load)
        m["cpu_clock_pct"] = int(clock_pct)
        m["cpu_name"] = ""
        m["cpu_token"] = ""
        m["cpu_rank"] = 0
        m["cpu_rank_name"] = ""
        m["cpu_upgrade"] = {}

        # Top CPU-time processes
        procs = sorted(psutil.process_iter(["name", "cpu_times"]),
                       key=lambda p: (p.info["cpu_times"].user + p.info["cpu_times"].system) if p.info["cpu_times"] else 0,
                       reverse=True)[:3]
        m["top_cpu"] = ", ".join(sorted(set(p.info["name"] for p in procs if p.info["name"])))

        uptime = time.time() - psutil.boot_time()
        m["uptime_days"] = round(uptime / 86400, 1)

        self._wmi_query("Win32_Processor", [
            "Name", "NumberOfCores", "NumberOfLogicalProcessors",
            "MaxClockSpeed", "CurrentClockSpeed", "SocketDesignation"
        ], lambda row: (
            m.update({
                "cpu_name": (row.get("Name") or "").strip(),
                "cpu_cores": int(row.get("NumberOfCores") or m.get("cpu_cores", 0)),
                "cpu_threads": int(row.get("NumberOfLogicalProcessors") or m.get("cpu_threads", 0)),
                "cpu_max_mhz": int(row.get("MaxClockSpeed") or m.get("cpu_max_mhz", 0)),
                "cpu_current_mhz": int(row.get("CurrentClockSpeed") or m.get("cpu_current_mhz", 0)),
                "cpu_socket": str(row.get("SocketDesignation") or ""),
            })
        ))

        # CPU rank lookup
        cpu_name = m.get("cpu_name", "")
        if cpu_name:
            token = self._cpu_token(cpu_name)
            m["cpu_token"] = token
            if token:
                from catalogs.cpus import find
                entry = find(token)
            else:
                from catalogs.cpus import find
                entry = find(cpu_name)
            if entry:
                m["cpu_rank"] = entry.rank
                m["cpu_rank_name"] = entry.name

        # CPU upgrade advice
        m["cpu_upgrade"] = self._cpu_advice(m)

    def _cpu_token(self, name: str) -> str:
        n = name.upper()
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

    def _cpu_advice(self, m: dict) -> dict:
        from scoring.cpu_advisor import advise
        return advise(
            m.get("cpu_name", ""),
            m.get("board_name", ""),
            m.get("cpu_socket", ""),
            m.get("has_dedicated_gpu", False),
            m.get("is_laptop", False),
        )

    # ---- GPU ----
    def _gpu(self, m: dict):
        m["gpus"] = []
        m["gpu_details"] = []
        m["has_dedicated_gpu"] = False
        m["vram_gb"] = 0
        m["gpu_driver_age_days"] = 0
        m["gpu_problem_count"] = 0
        m["gpu_rank"] = 0
        m["gpu_rank_name"] = ""

        try:
            import wmi
            c = wmi.WMI()
            for g in c.Win32_VideoController():
                if not g.Name:
                    continue
                name = g.Name.strip()
                m["gpus"].append(name)
                m["gpu_details"].append({
                    "name": name,
                    "dedicated": bool(re.search(r"NVIDIA|GeForce|RTX|GTX|Radeon RX|Radeon Pro|Quadro|Arc A|Arc B|Intel\(R\) Arc", name)),
                    "vram_gb": round(int(g.AdapterRAM or 0) / (1024**3), 1),
                    "driver_version": g.DriverVersion or "",
                    "driver_age_days": _age_days(g.DriverDate),
                })
                if re.search(r"NVIDIA|GeForce|RTX|GTX|Radeon RX|Radeon Pro|Quadro|Arc A|Arc B", name):
                    m["has_dedicated_gpu"] = True
                vram = round(int(g.AdapterRAM or 0) / (1024**3), 1)
                if vram > m["vram_gb"]:
                    m["vram_gb"] = vram
                age = _age_days(g.DriverDate) or 0
                if age > m["gpu_driver_age_days"]:
                    m["gpu_driver_age_days"] = age
                err = int(g.ConfigManagerErrorCode or 0)
                if err != 0:
                    m["gpu_problem_count"] += 1
        except Exception:
            # fallback via psutil
            try:
                sensors = psutil.sensors_temperatures()
            except Exception:
                pass

        # GPU rank
        if m["gpus"]:
            from catalogs.gpus import find as find_gpu
            best_rank = 0
            for gname in m["gpus"]:
                entry = find_gpu(gname)
                if entry and entry.rank > best_rank:
                    best_rank = entry.rank
            m["gpu_rank"] = best_rank

    # ---- Startup ----
    def _startup(self, m: dict):
        items = []
        for hive in [
            r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
            r"HKEY_CURRENT_USER\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
            r"HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
        ]:
            try:
                import winreg
                reg = winreg.ConnectRegistry(None, (
                    winreg.HKEY_LOCAL_MACHINE if "LOCAL_MACHINE" in hive else winreg.HKEY_CURRENT_USER
                ))
                parts = hive.split("\\")
                key = winreg.OpenKey(reg, "\\".join(parts[2:]))
                i = 0
                while True:
                    try:
                        name, _, _ = winreg.EnumValue(key, i)[0:3]
                        if not name.startswith("PS"):
                            items.append(name)
                    except OSError:
                        break
                    i += 1
                winreg.CloseKey(key)
            except Exception:
                pass

        sf = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
        if os.path.isdir(sf):
            for f in os.listdir(sf):
                if os.path.isfile(os.path.join(sf, f)):
                    items.append(os.path.splitext(f)[0])

        m["startup_count"] = len(items)
        m["startup_names"] = ", ".join(items[:12])

    # ---- Background ----
    def _background(self, m: dict):
        # Services
        svc_names = []
        try:
            for svc in psutil.win_service_iter():
                info = svc.as_dict()
                if (info.get("start_type") == "automatic" and
                    info.get("status") == "running" and
                    info.get("binpath") and
                    "\\Windows\\" not in (info.get("binpath") or "")):
                    svc_names.append(info.get("display_name") or info.get("name", ""))
        except Exception:
            pass
        m["third_party_service_count"] = len(svc_names)
        m["third_party_service_names"] = ", ".join(svc_names[:12])

        # Scheduled tasks (non-Microsoft). Keep the CSV header so DictReader
        # maps columns correctly (do NOT pass /NH), and de-duplicate tasks
        # that appear once per trigger.
        task_names = []
        try:
            out = subprocess.run(
                ["schtasks", "/Query", "/FO", "CSV"],
                capture_output=True, text=True, timeout=20, creationflags=0x08000000
            )
            if out.returncode == 0:
                import csv, io
                reader = csv.DictReader(io.StringIO(out.stdout))
                seen = set()
                for row in reader:
                    path = (row.get("TaskName") or "").strip()
                    status = (row.get("Status") or "").strip()
                    if not path or path == "TaskName":
                        continue  # blank line or a repeated header row
                    if path.startswith("\\Microsoft\\") or path in seen:
                        continue
                    if status in ("Ready", "Running"):
                        seen.add(path)
                        task_names.append(path.split("\\")[-1])
        except Exception:
            pass
        m["scheduled_task_count"] = len(task_names)
        m["scheduled_task_names"] = ", ".join(task_names[:12])

    # ---- Power ----
    def _power(self, m: dict):
        m["power_plan"] = "Unknown"
        m["power_saver"] = False
        m["on_battery"] = False
        m["battery_present"] = False
        m["thermal_temp_c"] = 0

        try:
            r = subprocess.run(
                ["powercfg", "/getactivescheme"],
                capture_output=True, text=True, timeout=5, creationflags=0x08000000
            )
            if r.returncode == 0:
                out_txt = r.stdout.strip()
                # powercfg prints: "Power Scheme GUID: <guid>  (Balanced)"
                friendly = re.search(r"\(([^)]+)\)\s*$", out_txt)
                m["power_plan"] = friendly.group(1) if friendly else out_txt
                m["power_saver"] = "power saver" in out_txt.lower()
        except Exception:
            pass

        bat = _try(lambda: psutil.sensors_battery(), None)
        if bat:
            m["battery_present"] = True
            m["on_battery"] = not bat.power_plugged

        try:
            import wmi
            c = wmi.WMI(namespace="root\\wmi")
            temps = []
            for tz in c.MSAcpi_ThermalZoneTemperature():
                val = (tz.CurrentTemperature or 0) / 10 - 273.15
                if 0 < val < 125:
                    temps.append(val)
            if temps:
                m["thermal_temp_c"] = round(max(temps), 1)
        except Exception:
            pass

    # ---- Drivers / Devices ----
    def _drivers(self, m: dict):
        m["problem_device_count"] = 0
        m["problem_device_names"] = ""
        m["old_driver_count"] = 0
        m["old_driver_names"] = ""

        try:
            import wmi
            c = wmi.WMI()
            bad = []
            for dev in c.Win32_PnPEntity():
                err = int(dev.ConfigManagerErrorCode or 0)
                if err != 0:
                    bad.append(dev.Name or "Unknown")
            m["problem_device_count"] = len(bad)
            m["problem_device_names"] = ", ".join(bad[:8])
        except Exception:
            pass

        cutoff = datetime.now() - timedelta(days=5 * 365)
        old = []
        try:
            import wmi
            c = wmi.WMI()
            for drv in c.Win32_PnPSignedDriver():
                if not drv.DeviceClass:
                    continue
                cls = drv.DeviceClass.upper()
                if cls not in ("DISPLAY", "NET", "HDC", "SCSIADAPTER", "SYSTEM", "MEDIA"):
                    continue
                provider = drv.DriverProviderName or ""
                if "Microsoft" in provider:
                    continue
                d = _cim_date_to_dt(drv.DriverDate)
                if d and d < cutoff:
                    old.append(f"{drv.DeviceName} ({drv.DeviceClass})")
            m["old_driver_count"] = len(old)
            m["old_driver_names"] = ", ".join(old[:8])
        except Exception:
            pass

    # ---- Updates ----
    def _updates(self, m: dict):
        m["last_update_days"] = None
        m["reboot_pending"] = False
        m["update_services_stopped"] = []

        # Windows Update via COM
        try:
            from ctypes import windll
            import comtypes.client
            au = comtypes.client.CreateObject("Microsoft.Update.AutoUpdate")
            res = au.Results
            if res and res.LastInstallationSuccessDate:
                last = _cim_date_to_dt(res.LastInstallationSuccessDate)
                if last:
                    m["last_update_days"] = max(0, (datetime.now() - last).days)
        except Exception:
            pass

        if m["last_update_days"] is None:
            try:
                import winreg
                key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\Results\Install"
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                val, _ = winreg.QueryValueEx(key, "LastSuccessTime")
                winreg.CloseKey(key)
                parsed = _cim_date_to_dt(val)
                if parsed:
                    m["last_update_days"] = max(0, (datetime.now() - parsed).days)
            except Exception:
                pass

        for key_path in [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
        ]:
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                winreg.CloseKey(key)
                m["reboot_pending"] = True
                break
            except FileNotFoundError:
                pass
            except Exception:
                pass

        for svc_name in ("wuauserv", "bits"):
            try:
                svc = psutil.win_service_get(svc_name)
                info = svc.as_dict()
                if info.get("status") != "running":
                    m["update_services_stopped"].append(svc_name)
            except Exception:
                pass

    # ---- Network ----
    def _network(self, m: dict):
        m["net_link_mbps"] = 0
        m["network_names"] = ""
        m["wifi_signal_pct"] = 0

        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        max_link = 0
        names = []
        for name, snics in addrs.items():
            if name in stats and stats[name].isup:
                speed = stats[name].speed  # Mbps, or -1
                if speed > 0:
                    max_link = max(max_link, speed)
                names.append(name)

        m["net_link_mbps"] = max_link
        m["network_names"] = ", ".join(names[:5])

        try:
            out = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, timeout=5, creationflags=0x08000000
            )
            for line in out.stdout.splitlines():
                if "Signal" in line and ":" in line:
                    pct = line.split(":")[-1].strip().rstrip("%")
                    try:
                        m["wifi_signal_pct"] = int(pct)
                    except ValueError:
                        pass
        except Exception:
            pass

        # Browser extensions & cache
        m["browser_ext_count"] = 0
        m["browser_cache_gb"] = 0.0
        roots = [
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data"),
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data"),
        ]
        for root in roots:
            if not os.path.isdir(root):
                continue
            for pdir in os.listdir(root):
                if pdir != "Default" and not pdir.startswith("Profile"):
                    continue
                p0 = os.path.join(root, pdir)
                ext_path = os.path.join(p0, "Extensions")
                if os.path.isdir(ext_path):
                    try:
                        m["browser_ext_count"] += len(os.listdir(ext_path))
                    except OSError:
                        pass
                for cn in ("Cache", "Code Cache", "GPUCache",
                           os.path.join("Service Worker", "CacheStorage")):
                    m["browser_cache_gb"] += _folder_gb(os.path.join(p0, cn), 2)

        ff_root = os.path.expandvars(r"%APPDATA%\Mozilla\Firefox\Profiles")
        if os.path.isdir(ff_root):
            for fp in os.listdir(ff_root):
                ej = os.path.join(ff_root, fp, "extensions.json")
                if os.path.isfile(ej):
                    try:
                        import json
                        with open(ej) as fh:
                            data = json.load(fh)
                        m["browser_ext_count"] += sum(1 for a in data.get("addons", []) if a.get("active"))
                    except Exception:
                        pass
                m["browser_cache_gb"] += _folder_gb(os.path.join(ff_root, fp, "cache2"), 2)

        m["browser_cache_gb"] = round(m["browser_cache_gb"], 2)

    # ---- Stability ----
    def _stability(self, m: dict):
        m["system_error_count"] = 0
        m["disk_event_count"] = 0
        m["whea_event_count"] = 0
        m["bug_check_count"] = 0
        m["app_crash_count"] = 0

        since = datetime.now() - timedelta(days=7)
        try:
            import win32evtlog
            hand = win32evtlog.OpenEventLog(None, "System")
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            sys_events = []
            while True:
                events = win32evtlog.ReadEventLog(hand, flags, 0)
                if not events:
                    break
                for ev in events:
                    if ev.TimeGenerated < since:
                        break
                    if ev.EventType in (win32evtlog.EVENTLOG_ERROR_TYPE, win32evtlog.EVENTLOG_WARNING_TYPE):
                        sys_events.append(ev)
            win32evtlog.CloseEventLog(hand)

            m["system_error_count"] = len(sys_events)
            m["disk_event_count"] = sum(
                1 for e in sys_events
                if re.search(r"disk|storahci|stornvme|ntfs|volmgr",
                             e.SourceName or "", re.IGNORECASE)
            )
            m["whea_event_count"] = sum(
                1 for e in sys_events
                if "WHEA" in (e.SourceName or "")
            )
            m["bug_check_count"] = sum(
                1 for e in sys_events
                if e.EventID == 1001 or "BugCheck" in (e.SourceName or "")
            )
        except Exception:
            # fallback: fewer events via PowerShell
            try:
                out = subprocess.run(
                    ["powershell", "-Command",
                     "Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2; StartTime=(Get-Date).AddDays(-7)} -MaxEvents 200 -ErrorAction SilentlyContinue | Measure-Object | Select-Object -ExpandProperty Count"],
                    capture_output=True, text=True, timeout=15, creationflags=0x08000000
                )
                if out.returncode == 0:
                    m["system_error_count"] = int(out.stdout.strip() or 0)
            except Exception:
                pass

        # App crashes
        try:
            out = subprocess.run(
                ["powershell", "-Command",
                 "Get-WinEvent -FilterHashtable @{LogName='Application'; Level=2; StartTime=(Get-Date).AddDays(-7)} -MaxEvents 100 -EA SilentlyContinue | Where-Object { $_.ProviderName -match 'Application Error|Windows Error Reporting|Application Hang' } | Measure-Object | Select-Object -ExpandProperty Count"],
                capture_output=True, text=True, timeout=15, creationflags=0x08000000
            )
            if out.returncode == 0:
                m["app_crash_count"] = int(out.stdout.strip() or 0)
        except Exception:
            pass

    # ---- Security ----
    def _security(self, m: dict):
        m["av_enabled"] = True
        m["realtime_protection"] = True
        m["defs_age_days"] = 0
        m["suspicious_count"] = 0
        m["suspicious_list"] = []
        m["hosts_custom_entries"] = 0

        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Microsoft\Windows Defender\Antivirus")
            val, _ = winreg.QueryValueEx(key, "DisableAntiSpyware")
            winreg.CloseKey(key)
            m["av_enabled"] = val == 0
        except Exception:
            try:
                import wmi
                c = wmi.WMI(namespace="root\\SecurityCenter2")
                for av in c.AntivirusProduct():
                    m["av_enabled"] = True
                    break
            except Exception:
                pass

        try:
            import wmi
            c = wmi.WMI(namespace="root\\SecurityCenter2")
            for mp in c.WmiSecurityCenter() or []:
                if hasattr(mp, "RealTimeProtectionEnabled"):
                    m["realtime_protection"] = bool(mp.RealTimeProtectionEnabled)
                    break
        except Exception:
            pass

        try:
            import wmi
            c = wmi.WMI()
            for mp in c.Win32_Product():
                if "Microsoft" in (mp.Name or "") and "Defender" in (mp.Name or ""):
                    break
        except Exception:
            pass

        try:
            out = subprocess.run(
                ["powershell", "-Command",
                 "Get-MpComputerStatus | Select-Object RealTimeProtectionEnabled, AntivirusEnabled, AntivirusSignatureAge | ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=10, creationflags=0x08000000
            )
            if out.returncode == 0 and out.stdout.strip():
                import json
                d = json.loads(out.stdout)
                m["av_enabled"] = d.get("AntivirusEnabled", True)
                m["realtime_protection"] = d.get("RealTimeProtectionEnabled", True)
                m["defs_age_days"] = int(d.get("AntivirusSignatureAge", 0) or 0)
        except Exception:
            pass

        # Suspicious file scan
        import tempfile
        doc_ext = re.compile(r"\.(pdf|doc|docx|xls|xlsx|ppt|pptx|txt|rtf|jpg|jpeg|png|gif|zip|rar|csv|htm|html)$", re.IGNORECASE)
        exe_ext = re.compile(r"\.(exe|scr|com|pif|bat|cmd|vbs|js|jse|wsf|ps1)$", re.IGNORECASE)
        double_ext = re.compile(r"\.(pdf|doc|docx|xls|xlsx|ppt|pptx|txt|rtf|jpg|jpeg|png|gif|zip|rar|csv)\.(exe|scr|com|pif|bat|cmd|vbs|js|jse|wsf|ps1)$", re.IGNORECASE)

        sus_list = []
        scan_dirs = list(dict.fromkeys([
            tempfile.gettempdir(),
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Temp"),
            os.path.expanduser("~/Downloads"),
            os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup"),
            os.path.join(os.environ.get("PROGRAMDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup"),
        ]))

        for d in scan_dirs:
            if not os.path.isdir(d):
                continue
            is_startup = "startup" in d.lower()
            try:
                for f in os.listdir(d):
                    fp = os.path.join(d, f)
                    if not os.path.isfile(fp):
                        continue
                    if not exe_ext.search(f):
                        continue
                    reasons = []
                    if double_ext.search(f):
                        reasons.append("disguised double extension")
                    if is_startup:
                        if re.search(r"\.(vbs|js|jse|bat|cmd|ps1|wsf)$", f, re.IGNORECASE):
                            reasons.append("script set to run at startup")
                        else:
                            from ctypes import windll
                            sig = _try(lambda: windll.wintrust.WinVerifyTrust(0, None, fp), None)
                            if sig and sig != 0:
                                reasons.append("unsigned item set to auto-start")
                    elif "\\temp\\" in fp.lower() and re.search(r"\.(exe|scr|com|pif)$", f, re.IGNORECASE):
                        from ctypes import windll
                        sig = _try(lambda: windll.wintrust.WinVerifyTrust(0, None, fp), None)
                        if sig and sig != 0:
                            reasons.append("unsigned executable in a Temp folder")
                    if reasons:
                        sus_list.append(f"{fp} [{'; '.join(reasons)}]")
            except Exception:
                pass

        m["suspicious_count"] = len(sus_list)
        m["suspicious_list"] = sus_list[:12]

        # Hosts file
        hosts = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32", "drivers", "etc", "hosts")
        if os.path.isfile(hosts):
            try:
                with open(hosts) as fh:
                    lines = [
                        l for l in fh
                        if l.strip() and not l.strip().startswith("#")
                        and "localhost" not in l.lower()
                    ]
                m["hosts_custom_entries"] = len(lines)
            except Exception:
                pass

    # ---- WMI helper ----
    def _wmi_query(self, wmi_class: str, fields: list, handler):
        try:
            import wmi
            c = wmi.WMI()
            for row in c.query(f"SELECT {','.join(fields)} FROM {wmi_class}"):
                row_dict = {f: getattr(row, f, None) for f in fields}
                handler(row_dict)
                return
        except Exception:
            # Fallback: PowerShell
            try:
                ps_cmd = (
                    f"Get-CimInstance {wmi_class} | Select-Object "
                    f"{','.join(fields)} | ConvertTo-Json -Compress"
                )
                r = subprocess.run(
                    ["powershell", "-Command", ps_cmd],
                    capture_output=True, text=True, timeout=15, creationflags=0x08000000
                )
                if r.returncode == 0 and r.stdout.strip():
                    import json
                    data = json.loads(r.stdout)
                    if isinstance(data, dict):
                        data = [data]
                    handler({f: data[0].get(f) for f in fields})
            except Exception:
                pass
