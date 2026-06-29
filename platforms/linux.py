"""Linux metric collector."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

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
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except Exception:
        pass
    return round(total / (1024 ** 3), 2)


class LinuxCollector(MetricCollector):
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
        m["os"] = "Linux"
        m["os_build"] = ""
        m["board_name"] = ""
        m["cpu_socket"] = ""
        m["bios_age_days"] = None
        m["is_laptop"] = False

        lsb = _run_json(["lsb_release", "-a", "-j"])
        if isinstance(lsb, dict):
            m["os"] = f"{lsb.get('DistributorID', '')} {lsb.get('Description', '')}".strip()
            m["os_build"] = lsb.get("Release", "")

        # Board info from dmidecode (requires root)
        dmidecode = _run(["dmidecode", "-t", "baseboard"])
        if dmidecode:
            m_manufacturer = re.search(r"Manufacturer:\s*(.+)", dmidecode)
            m_product = re.search(r"Product Name:\s*(.+)", dmidecode)
            if m_manufacturer:
                m["board_name"] = m_manufacturer.group(1).strip()
            if m_product:
                m["board_name"] += " " + m_product.group(1).strip()
            m["board_name"] = m["board_name"].strip()

        # Laptop check
        try:
            chassis = _run(["cat", "/sys/class/chassis/type"]).strip().lower()
            m["is_laptop"] = chassis in ("laptop", "notebook", "portable")
        except Exception:
            pass
        if not m["is_laptop"]:
            # check via systemd
            on_ac = _run(["cat", "/sys/class/power_supply/AC/online"]).strip()
            m["is_laptop"] = bool(_run(["find", "/sys/class/power_supply", "-name", "BAT*"]))

        # CPU socket from lscpu
        lscpu = _run_json(["lscpu"])
        if isinstance(lscpu, dict):
            m["cpu_socket"] = lscpu.get("Socket(s)", "")
            if not m.get("cpu_name"):
                m["cpu_name"] = lscpu.get("Model name", "")
                m["cpu_cores"] = int(lscpu.get("Core(s) per socket", lscpu.get("CPU(s)", 0)))
                m["cpu_threads"] = int(lscpu.get("CPU(s)", psutil.cpu_count(logical=True) or 0))

        # BIOS age
        try:
            bi = _run(["dmidecode", "-t", "bios"])
            m_ver = re.search(r"BIOS Revision:\s*(.+)", bi)
            if m_ver:
                # use mtime of /var/log/dmesg as a rough proxy
                dmesg_mtime = _try(lambda: os.path.getmtime("/var/log/dmesg"), None)
                if dmesg_mtime:
                    m["bios_age_days"] = int((datetime.now().timestamp() - dmesg_mtime) / 86400)
        except Exception:
            pass

    # ---- Memory ----
    def _memory(self, m: dict):
        vm = psutil.virtual_memory()
        m["ram_total_gb"] = round(vm.total / (1024**3), 1)
        m["ram_used_pct"] = vm.percent
        total_virt = vm.total + psutil.swap_memory().total
        used_virt = vm.used + psutil.swap_memory().used
        m["commit_used_pct"] = round(used_virt / total_virt * 100, 0) if total_virt else 0

        procs = sorted(psutil.process_iter(["name", "memory_info"]),
                       key=lambda p: p.info["memory_info"].rss or 0, reverse=True)[:5]
        m["top_mem"] = ", ".join(
            f"{p.info['name']} ({round((p.info['memory_info'].rss or 0) / 1024**3, 1)} GB)"
            for p in procs
        )
        m["top_mem_gb"] = round((procs[0].info["memory_info"].rss or 0) / 1024**3, 1) if procs else 0

        m["ram_slots_used"] = 0
        m["ram_slots_total"] = 0
        m["ram_type"] = "RAM"
        m["ram_form"] = "laptop" if m.get("is_laptop") else "desktop"

        dmidecode = _run(["dmidecode", "-t", "memory"])
        if dmidecode:
            lines = dmidecode.splitlines()
            current = None
            for line in lines:
                m_size = re.match(r"\s*Size:\s*(\d+)\s*MB", line)
                if m_size:
                    if int(m_size.group(1)) > 0:
                        current = m_size.group(1)
                        m["ram_slots_used"] = m.get("ram_slots_used", 0) + 1
                m_dev = re.search(r"Memory Device", line)
                if m_dev:
                    m["ram_slots_used"] = m.get("ram_slots_used", 0) + (1 if current else 0)
                    current = None
                m_type = re.search(r"(DDR[0-9]+|DDR[0-9]+[A-Z]*)", line)
                if m_type and "Type:" in line:
                    m["ram_type"] = m_type.group(1)
            m["ram_slots_total"] = m["ram_slots_used"]

    # ---- Storage ----
    def _storage(self, m: dict):
        sys_drive = "/"
        try:
            ld = psutil.disk_usage(sys_drive)
            m["sys_size_gb"] = round(ld.total / 1024**3, 1)
            m["sys_free_gb"] = round(ld.free / 1024**3, 1)
            m["sys_free_pct"] = round(ld.free / ld.total * 100, 0) if ld.total else 100
        except Exception:
            m["sys_size_gb"] = 0
            m["sys_free_gb"] = 0
            m["sys_free_pct"] = 100

        temp_dirs = [
            os.environ.get("TEMP", "/tmp"),
            "/tmp",
        ]
        tb = sum(_folder_gb(d, 2) for d in temp_dirs if d)
        m["temp_gb"] = round(tb, 2)
        m["recycle_gb"] = 0.0

    # ---- Disk Speed/Health ----
    def _disk(self, m: dict):
        m["sys_is_hdd"] = False
        m["secondary_hdds"] = []
        m["has_ssd"] = False
        m["disk_health_bad"] = []
        m["disk_busy_pct"] = 0
        m["trim_disabled"] = False

        lsblk = _run_json(["lsblk", "-d", "-o", "NAME,TYPE,SIZE,ROTA,TRAN", "-J"])
        if isinstance(lsblk, dict) and "blockdevices" in lsblk:
            for dev in lsblk["blockdevices"]:
                if dev.get("type") != "disk":
                    continue
                name = dev.get("name", "")
                rota = dev.get("rota", 1)
                if not rota:  # SSD
                    m["has_ssd"] = True
                if rota:
                    size = dev.get("size", "?")
                    m["secondary_hdds"].append(f"/dev/{name} ({size})")

        # sys.is_hdd: check root device
        root_dev = os.path.realpath("/")
        df = _run(["df", "-T", "-P", "/"])
        for line in df.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 7:
                fstype = parts[1]
                dev = parts[0]
                if fstype in ("ext4", "xfs", "btrfs", "ext3", "ext2"):
                    # check if the block device is rotational
                    short = dev.rsplit("/", 1)[-1].rstrip("0123456789")
                    rot = _run(["cat", f"/sys/block/{short}/queue/rotational"]).strip()
                    if rot == "0":
                        m["has_ssd"] = True
                    else:
                        m["sys_is_hdd"] = True

        # SMART (via smartctl)
        smart_status = _run(["smartctl", "-H", "/dev/disk/by-id/ata-0"])
        if "PASSED" in smart_status or "OK" in smart_status:
            pass
        elif "FAILED" in smart_status:
            m["disk_health_bad"].append("SMART self-assessment: FAILED")
        elif smart_status:
            m["disk_health_bad"].append("SMART check returned: unknown")

        # Disk busy from iostat
        iostat = _run(["iostat", "-c", "1", "2"])
        for line in iostat.splitlines():
            if "idle" in line.lower():
                parts = line.split()
                try:
                    busy_pct = 100 - float(parts[-1])
                    m["disk_busy_pct"] = int(busy_pct)
                except (IndexError, ValueError):
                    pass
                break

        # TRIM support
        trim = _run(["cat", "/sys/block/sda/queue/discard_granularity"]).strip()
        m["trim_disabled"] = trim == "0" if trim else False

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

        lscpu = _run_json(["lscpu"])
        if isinstance(lscpu, dict):
            m["cpu_name"] = lscpu.get("Model name", "")

        procs = sorted(psutil.process_iter(["name", "cpu_times"]),
                       key=lambda p: (p.info["cpu_times"].user + p.info["cpu_times"].system)
                       if p.info["cpu_times"] else 0, reverse=True)[:3]
        m["top_cpu"] = ", ".join(sorted(set(p.info["name"] for p in procs if p.info["name"])))

        m["uptime_days"] = round((datetime.now().timestamp() - psutil.boot_time()) / 86400, 1)

        # CPU rank
        if m["cpu_name"]:
            from catalogs.cpus import find
            token = self._cpu_token(m["cpu_name"])
            m["cpu_token"] = token
            entry = find(token) if token else find(m["cpu_name"])
            if entry:
                m["cpu_rank"] = entry.rank
                m["cpu_rank_name"] = entry.name

        # CPU upgrade
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

        lspci = _run(["lspci", "-k", "-nn"])
        drm_path = "/sys/class/drm"
        gpu_idx = 0

        if os.path.isdir(drm_path):
            for entry in sorted(os.listdir(drm_path)):
                if not re.match(r"^card\d+$", entry):
                    continue
                card_path = os.path.join(drm_path, entry)
                device = os.path.join(card_path, "device")
                vendor_path = os.path.join(device, "vendor")
                model_path = os.path.join(device, "device")
                if not os.path.isfile(vendor_path):
                    continue

                try:
                    vendor_id = open(vendor_path).read().strip()
                    device_id = open(model_path).read().strip() if os.path.isfile(model_path) else "0000"
                except OSError:
                    continue

                name = ""
                # Parse lspci for name
                for pline in lspci.splitlines():
                    if device_id in pline:
                        # format: 01:00.0 VGA [0300]: NVIDIA ...
                        parts = pline.split("]", 1)
                        if len(parts) == 2:
                            name = parts[1].split("(", 1)[0].strip()
                        break
                if not name:
                    vendor_map = {
                        "0x8086": "Intel",
                        "0x10de": "NVIDIA",
                        "0x1002": "AMD",
                    }
                    name = f"{vendor_map.get(vendor_id, vendor_id)} Graphics [{entry}]"

                dedicated = bool(re.search(r"NVIDIA|RTX|GTX|Quadro|Radeon RX|Radeon Pro|Arc", name))
                m["gpus"].append(name)
                m["gpu_details"].append({
                    "name": name, "dedicated": dedicated,
                    "vram_gb": 0, "driver_version": "", "driver_age_days": 0,
                })
                if dedicated:
                    m["has_dedicated_gpu"] = True
                m["gpu_idx"] = getattr(m, "gpu_idx", 0) + 1

                # VRAM from sysfs
                mem_info_path = os.path.join(device, "mem_info_vram")
                if os.path.isfile(mem_info_path):
                    try:
                        vram_bytes = int(open(mem_info_path).read().strip())
                        vram_gb = round(vram_bytes / 1024**3, 1)
                        if vram_gb > m["vram_gb"]:
                            m["vram_gb"] = vram_gb
                        m["gpu_details"][-1]["vram_gb"] = vram_gb
                    except (OSError, ValueError):
                        pass

                # Shared VRAM for iGPU
                if not dedicated:
                    mem_info_gtt = os.path.join(device, "mem_info_gtt")
                    if os.path.isfile(mem_info_gtt):
                        try:
                            gtt = int(open(mem_info_gtt).read().strip())
                            gtt_gb = round(gtt / 1024**3, 1)
                            if gtt_gb > m["vram_gb"]:
                                m["vram_gb"] = gtt_gb
                        except (OSError, ValueError):
                            pass

                gpu_idx += 1
        else:
            # fallback: glxinfo
            glx = _run(["glxinfo"])
            for line in glx.splitlines():
                if "OpenGL vendor" in line:
                    m["gpus"].append(line.split(":", 1)[-1].strip())
                if "OpenGL renderer" in line:
                    m["gpus"].append(line.split(":", 1)[-1].strip())

        # NVIDIA specific
        nvsmi = _run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                       "--format=csv,noheader,nounits"])
        if nvsmi:
            for line in nvsmi.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    name, vram_mb, drv = parts[0], parts[1], parts[2]
                    vram_gb = round(int(vram_mb) / 1024, 1)
                    m["gpus"] = [name]
                    m["vram_gb"] = vram_gb
                    m["has_dedicated_gpu"] = True
                    m["gpu_details"] = [{
                        "name": name, "dedicated": True,
                        "vram_gb": vram_gb, "driver_version": drv, "driver_age_days": 0,
                    }]

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
        # systemd user services
        units = _run(["systemctl", "--user", "list-unit-files", "--type=service", "--state=enabled", "--no-pager"])
        for line in units.splitlines()[1:]:
            if line.strip():
                items.append(line.split()[0])

        # XDG autostart
        autostart = os.path.expanduser("~/.config/autostart")
        if os.path.isdir(autostart):
            for f in os.listdir(autostart):
                if f.endswith(".desktop"):
                    items.append(f.replace(".desktop", ""))

        # Crontab (user)
        crontab = _run(["crontab", "-l"])
        for line in crontab.splitlines():
            if line.strip() and not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 7:
                    items.append(parts[6].split("/")[-1])
                elif len(parts) >= 6:
                    items.append(parts[5].split("/")[-1])

        m["startup_count"] = len(items)
        m["startup_names"] = ", ".join(items[:12])

    # ---- Background ----
    def _background(self, m: dict):
        # systemd services (user)
        svc_items = []
        out = _run(["systemctl", "--user", "list-units", "--type=service", "--state=running", "--no-pager", "--plain", "--no-legend"])
        for line in out.strip().splitlines():
            if line.strip():
                svc_items.append(line.split()[0])

        # system services (requires root)
        try:
            sys_out = _run(["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--plain", "--no-legend"])
            for line in sys_out.strip().splitlines():
                if line.strip():
                    parts = line.split()
                    if parts and not parts[0].startswith("systemd-") and not parts[0].startswith("dbus-"):
                        svc_items.append(parts[0])
        except Exception:
            pass

        m["third_party_service_count"] = len(svc_items)
        m["third_party_service_names"] = ", ".join(svc_items[:12])

        # Crontab entries
        task_items = []
        crontab = _run(["crontab", "-l"])
        for line in crontab.splitlines():
            if line.strip() and not line.startswith("#"):
                task_items.append(line.split()[-1].split("/")[-1])
        # system cron
        syscron = _run(["cat", "/etc/crontab"])
        for line in syscron.splitlines():
            if not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 7:
                    task_items.append(parts[6])
        # /etc/cron.d
        try:
            for f in os.listdir("/etc/cron.d"):
                task_items.append(f)
        except OSError:
            pass

        m["scheduled_task_count"] = len(task_items)
        m["scheduled_task_names"] = ", ".join(task_items[:12])

    # ---- Power ----
    def _power(self, m: dict):
        m["power_plan"] = "Linux"
        m["power_saver"] = False
        m["on_battery"] = False
        m["battery_present"] = False
        m["thermal_temp_c"] = 0

        # Battery
        bat = _try(lambda: psutil.sensors_battery(), None)
        if bat:
            m["battery_present"] = True
            m["on_battery"] = not bat.power_plugged

        # Thermal
        for zone in sorted(os.listdir("/sys/class/thermal")):
            if "thermal_zone" in zone:
                temp_path = f"/sys/class/thermal/{zone}/temp"
                if os.path.isfile(temp_path):
                    try:
                        val = int(open(temp_path).read().strip()) / 1000
                        if val > m["thermal_temp_c"]:
                            m["thermal_temp_c"] = round(val, 1)
                    except (OSError, ValueError):
                        pass

        # Power profile (systemd)
        try:
            r = subprocess.run(["powerprofilesctl", "get"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                profile = r.stdout.strip().lower()
                m["power_plan"] = profile.capitalize()
                m["power_saver"] = profile in ("power-saver", "power saver")
        except Exception:
            pass

    # ---- Drivers ----
    def _drivers(self, m: dict):
        m["problem_device_count"] = 0
        m["problem_device_names"] = ""
        m["old_driver_count"] = 0
        m["old_driver_names"] = ""

        dmesg = _run(["dmesg", "-T", "--level=err,warn"])
        errors = []
        for line in dmesg.splitlines():
            if "error" in line.lower() or "fail" in line.lower() or "warn" in line.lower():
                errors.append(line.strip())
        m["problem_device_count"] = len(errors[:20])
        m["problem_device_names"] = ", ".join(errors[:8])

        if not errors:
            lspci = _run(["lspci", "-k"])
            for line in lspci.splitlines():
                if "Kernel driver in use" in line:
                    break

    # ---- Updates ----
    def _updates(self, m: dict):
        m["last_update_days"] = None
        m["reboot_pending"] = False
        m["update_services_stopped"] = []

        # Check for apt
        if os.path.isfile("/var/lib/dpkg/last-update"):
            mtime = _try(lambda: os.path.getmtime("/var/lib/dpkg/last-update"), None)
            if mtime:
                m["last_update_days"] = int((datetime.now().timestamp() - mtime) / 86400)

        # dnf
        elif os.path.isfile("/var/log/dnf.log"):
            mtime = _try(lambda: os.path.getmtime("/var/log/dnf.log"), None)
            if mtime:
                m["last_update_days"] = int((datetime.now().timestamp() - mtime) / 86400)

        # pacman
        elif os.path.isfile("/var/log/pacman.log"):
            # last line with "upgraded"
            log = _run(["tail", "-100", "/var/log/pacman.log"])
            for line in reversed(log.splitlines()):
                if "starting full system upgrade" in line.lower() or "upgraded" in line:
                    # parse timestamp
                    m_ts = re.match(r"\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", line)
                    if m_ts:
                        try:
                            ts = datetime.strptime(m_ts.group(1), "%Y-%m-%d %H:%M")
                            m["last_update_days"] = int((datetime.now() - ts).total_seconds() / 86400)
                        except ValueError:
                            pass
                    break

        # Reboot pending
        m["reboot_pending"] = os.path.isfile("/var/run/reboot-required")

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

        # WiFi signal
        iw = _run(["iwconfig"])
        for line in iw.splitlines():
            if "Signal level" in line:
                m_sig = re.search(r"Signal level[=:]\s*(-?\d+)", line)
                if m_sig:
                    # WiFi signal is typically -100..0 dBm, convert to %
                    dbm = int(m_sig.group(1))
                    m["wifi_signal_pct"] = max(0, min(100, round((dbm + 100) * 2)))

        # Browsers
        self._scan_browsers(m)

    def _scan_browsers(self, m: dict):
        m["browser_ext_count"] = 0
        m["browser_cache_gb"] = 0.0
        doc_ext = re.compile(r"\.(pdf|doc|docx|xls|xlsx|ppt|pptx|txt|rtf|jpg|jpeg|png|gif|zip|rar|csv|htm|html)$", re.IGNORECASE)
        exe_ext = re.compile(r"\.(exe|scr|com|pif|bat|cmd|vbs|js|jse|wsf|ps1)$", re.IGNORECASE)
        double_ext = re.compile(r"\.(?:pdf|doc|docx|xls|xlsx|ppt|pptx|txt|rtf|jpg|jpeg|png|gif|zip|rar|csv)\.(?:exe|scr|com|pif|bat|cmd|vbs|js|jse|wsf|ps1)$", re.IGNORECASE)

        sus_list = []

        scan_dirs = [
            os.path.expanduser("~/Downloads"),
            os.path.expandvars("$TEMP"),
            os.path.expandvars("$TMP"),
            os.path.expanduser("~/Desktop"),
        ]
        if "XDG_CONFIG_HOME" in os.environ:
            scan_dirs.append(os.path.expandvars("$XDG_CONFIG_HOME/autostart"))

        for d in scan_dirs:
            if not d or not os.path.isdir(d):
                continue
            is_startup = "autostart" in d
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
                        reasons.append("script/executable in autostart")
                    if reasons:
                        sus_list.append(f"{fp} [{'; '.join(reasons)}]")
            except OSError:
                pass

        m["suspicious_count"] = len(sus_list)
        m["suspicious_list"] = sus_list[:12]
        m["hosts_custom_entries"] = 0

        # Browser detection
        config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        browser_roots = {
            "google-chrome": os.path.join(config_home, "google-chrome", "Default"),
            "chromium": os.path.join(config_home, "chromium", "Default"),
            "BraveSoftware/Brave-Browser": os.path.join(config_home, "BraveSoftware", "Brave-Browser", "Default"),
            "microsoft-edge": os.path.join(config_home, "microsoft-edge", "Default"),
            "Code/User": os.path.join(config_home, "Code", "User"),  # VS Code not a browser but has extensions
            "vivaldi": os.path.join(config_home, "vivaldi", "Default"),
            "opera": os.path.join(config_home, "opera", "Default"),
        }
        profiles_dirs = [
            os.path.join(config_home, "google-chrome"),
            os.path.join(config_home, "chromium"),
            os.path.join(config_home, "BraveSoftware", "Brave-Browser"),
            os.path.join(config_home, "microsoft-edge"),
            os.path.join(config_home, "vivaldi"),
            os.path.join(config_home, "opera"),
            os.path.expanduser("~/.mozilla/firefox"),
        ]
        for root in profiles_dirs:
            if not os.path.isdir(root):
                continue
            for pdir in os.listdir(root):
                if pdir == "Default" or re.match(r"^Profile \d+$", pdir):
                    p0 = os.path.join(root, pdir)
                    ext_path = os.path.join(p0, "Extensions")
                    if os.path.isdir(ext_path):
                        try:
                            m["browser_ext_count"] += len(os.listdir(ext_path))
                        except OSError:
                            pass
                    for cn in ("Cache", "Code Cache", "GPUCache"):
                        cache_path = os.path.join(p0, cn)
                        m["browser_cache_gb"] += _folder_gb(cache_path, 2)

                    # Firefox: extensions.json
                    ff_meta = os.path.join(p0, "extensions.json")
                    if os.path.isfile(ff_meta):
                        try:
                            with open(ff_meta) as fh:
                                data = json.load(fh)
                            addons = data.get("addons", [])
                            m["browser_ext_count"] += sum(1 for a in addons if a.get("active"))
                        except (OSError, json.JSONDecodeError):
                            pass
                    # Firefox cache2
                    cache2 = os.path.join(p0, "cache2")
                    m["browser_cache_gb"] += _folder_gb(cache2, 2)

        m["browser_cache_gb"] = round(m["browser_cache_gb"], 2)

    # ---- Stability ----
    def _stability(self, m: dict):
        m["system_error_count"] = 0
        m["disk_event_count"] = 0
        m["whea_event_count"] = 0
        m["bug_check_count"] = 0
        m["app_crash_count"] = 0

        # journalctl
        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        journal = _run(["journalctl", "--since", since, "-p", "warning", "--no-pager", "-q"])

        sys_errors = 0
        disk_ev = 0
        whea = 0
        for line in journal.splitlines():
            sys_errors += 1
            ll = line.lower()
            if any(kw in ll for kw in ("sd", "nvme", "ata", "scsi", "blk", "disk", "nvme", "ext4", "xfs", "btrfs")):
                disk_ev += 1
            if "whea" in ll or "mce" in ll:
                whea += 1

        m["system_error_count"] = sys_errors
        m["disk_event_count"] = disk_ev
        m["whea_event_count"] = whea
        m["bug_check_count"] = _run(["journalctl", "--since", since, "|", "grep", "-c", "panic"]).strip().count("\n")
        m["app_crash_count"] = _run([
            "journalctl", "--since", since, "-p", "err",
            "-g", "segfault|abort|crash", "--no-pager", "-q"
        ]).strip().count("\n")

    # ---- Security ----
    def _security(self, m: dict):
        m["av_enabled"] = True
        m["realtime_protection"] = True
        m["defs_age_days"] = 0
        m["suspicious_count"] = 0
        m["suspicious_list"] = []
        m["hosts_custom_entries"] = 0

        # ClamAV?
        clamscan = _run(["which", "clamscan"])
        if not clamscan.strip():
            m["av_enabled"] = False

        # Firewall: ufw/firewalld/nftables
        ufw = _run(["ufw", "status"])
        if "inactive" in ufw.lower() and "active" not in ufw.lower():
            pass  # ufw present but not active

        # Suspicious files in /tmp and ~/Downloads
        doc_ext = re.compile(r"\.(pdf|doc|docx|xls|xlsx|ppt|pptx|txt|rtf)$", re.IGNORECASE)
        exe_ext = re.compile(r"\.(exe|scr|com|pif|bat|cmd|vbs|js|jse|wsf|ps1|elf|so|dll)$", re.IGNORECASE)
        double_ext = re.compile(
            r"\.(?:pdf|doc|docx|xls|xlsx|ppt|pptx|txt|rtf|jpg|jpeg|png|gif|zip|rar|csv)"
            r"\.(?:exe|scr|com|pif|bat|cmd|vjs|jse|wsf|elf|sh)$",
            re.IGNORECASE,
        )

        sus = []
        for scan_dir in ["/tmp", os.path.expanduser("~/Downloads"), os.path.expanduser("~/Desktop")]:
            if not os.path.isdir(scan_dir):
                continue
            try:
                for f in os.listdir(scan_dir)[:200]:
                    fp = os.path.join(scan_dir, f)
                    if not os.path.isfile(fp):
                        continue
                    if not exe_ext.search(f):
                        continue
                    reasons = []
                    if double_ext.search(f):
                        reasons.append("disguised double extension")
                    if reasons:
                        sus.append(f"{fp} [{'; '.join(reasons)}]")
            except (OSError, PermissionError):
                pass

        m["suspicious_count"] = len(sus)
        m["suspicious_list"] = sus[:12]
