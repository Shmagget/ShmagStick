"""Evidence-based enrichment for hardware and software recommendations."""

from __future__ import annotations

from core.models import CategoryResult, Upgrade


def enrich_upgrade(category: CategoryResult, metrics: dict, profile) -> None:
    upgrade = category.upgrade
    if not upgrade:
        return
    upgrade.upgrade_type = category.name
    upgrade.why = category.reason
    upgrade.priority = _priority(category)
    upgrade.compatibility_confidence = category.confidence
    if category.key == "memory":
        _memory(upgrade, metrics, profile)
    elif category.key in ("storage", "diskspeed"):
        _storage(upgrade, metrics)
    elif category.key == "cpu":
        _cpu(upgrade, metrics)
    elif category.key == "gpu":
        _gpu(upgrade, metrics, profile)
    else:
        upgrade.current_part = category.stat
        upgrade.minimum_target = "Apply the recommended software or maintenance fix"
        upgrade.better_target = "Re-scan after the fix to confirm improvement"
        upgrade.compatibility_confidence = "High"
        upgrade.diy_friendly = "Yes"


def _memory(upgrade: Upgrade, metrics: dict, profile) -> None:
    total = metrics.get("ram_total_gb")
    ram_type = metrics.get("ram_type") or "type unavailable"
    upgrade.current_part = f"{total} GB {ram_type}" if total else "Memory details unavailable"
    upgrade.minimum_target = f"{profile.ram_target_gb} GB total"
    upgrade.better_target = f"{max(profile.ram_target_gb * 2, 16)} GB total for extra headroom"
    if metrics.get("memory_upgradable") is False:
        upgrade.kind = "advisory"
        upgrade.url = ""
        upgrade.text = "Internal memory is fixed on this platform"
        upgrade.note = "Choose fewer concurrent workloads or consider replacement if memory pressure is persistent."
        upgrade.compatibility_confidence = "High"
        upgrade.verify_before_buying = ["Confirm the exact model before assuming internal memory is replaceable"]
        upgrade.diy_friendly = "No"
        return
    slots_total = metrics.get("ram_slots_total") or 0
    slots_used = metrics.get("ram_slots_used") or 0
    upgrade.compatibility_confidence = "Medium" if ram_type != "type unavailable" else "Low"
    upgrade.verify_before_buying = [
        "Memory generation and speed",
        "Maximum supported capacity",
        f"Available slots ({slots_used}/{slots_total} reported)" if slots_total else "Physical slot availability",
        "DIMM versus SO-DIMM form factor",
    ]
    upgrade.diy_friendly = "Usually" if not metrics.get("is_laptop") else "Model-dependent"


def _storage(upgrade: Upgrade, metrics: dict) -> None:
    disk_type = metrics.get("system_disk_type") or "Unknown"
    models = metrics.get("disk_models") or []
    upgrade.current_part = f"{disk_type}: {models[0]}" if models else disk_type
    upgrade.minimum_target = "Reliable SSD with enough space to keep at least 15-20% free"
    upgrade.better_target = "NVMe SSD when the computer has a compatible M.2 PCIe slot"
    if metrics.get("storage_upgradable") is False:
        upgrade.kind = "advisory"
        upgrade.url = ""
        upgrade.text = "Internal storage is not considered field-upgradable"
        upgrade.note = "Use external storage for capacity, or replace the computer if internal storage is the bottleneck."
        upgrade.compatibility_confidence = "High"
        upgrade.verify_before_buying = ["Exact model and external port speed", "Backup and migration plan"]
        upgrade.diy_friendly = "External storage only"
        return
    upgrade.compatibility_confidence = "Medium" if metrics.get("disk_type_known") else "Low"
    upgrade.verify_before_buying = [
        "2.5-inch SATA versus M.2 form factor",
        "M.2 SATA versus NVMe/PCIe protocol",
        "Physical length and available slot",
        "Backup, cloning, and operating-system recovery plan",
    ]
    upgrade.diy_friendly = "Usually" if not metrics.get("is_laptop") else "Model-dependent"


def _cpu(upgrade: Upgrade, metrics: dict) -> None:
    advice = metrics.get("cpu_upgrade") or {}
    upgrade.current_part = metrics.get("cpu_name") or "Processor unavailable"
    upgrade.minimum_target = "A processor that resolves the measured core/load bottleneck"
    upgrade.better_target = advice.get("recommended") or "Replacement platform if no worthwhile compatible CPU exists"
    confidence = str(advice.get("confidence") or "low").lower()
    upgrade.compatibility_confidence = (
        "High" if "board compatibility" in confidence or "soldered" in confidence
        else "Medium" if "detected" in confidence else "Low"
    )
    upgrade.verify_before_buying = [
        "Exact motherboard CPU support list",
        "Required BIOS version",
        "Cooling capacity and power limits",
        "Socket alone does not guarantee compatibility",
    ]
    upgrade.diy_friendly = "No" if not advice.get("can_buy") else "Advanced"


def _gpu(upgrade: Upgrade, metrics: dict, profile) -> None:
    upgrade.current_part = ", ".join(metrics.get("gpus") or []) or "Graphics hardware unavailable"
    upgrade.minimum_target = f"Workload-appropriate GPU with {profile.gpu_vram_target}+ GB dedicated VRAM where applicable"
    upgrade.better_target = "A balanced GPU within the system's power, thermal, and CPU limits"
    fixed = metrics.get("is_laptop") or metrics.get("apple_silicon")
    if fixed:
        upgrade.kind = "advisory"
        upgrade.url = ""
        upgrade.compatibility_confidence = "High"
        upgrade.verify_before_buying = ["External GPU support on the exact model", "Application support for the target GPU"]
        upgrade.diy_friendly = "No internal upgrade"
    else:
        upgrade.compatibility_confidence = "Low"
        upgrade.verify_before_buying = [
            "Power-supply wattage and connectors",
            "Case length, height, and slot clearance",
            "Free PCIe x16 slot",
            "CPU balance and display connectors",
        ]
        upgrade.diy_friendly = "Moderate"


def _priority(category: CategoryResult) -> str:
    if category.score < 40 or any(f.severity == "Critical" for f in category.findings):
        return "Critical"
    if category.score < 60 or any(f.severity == "High" for f in category.findings):
        return "High"
    if category.score < 80:
        return "Medium"
    return "Low"
