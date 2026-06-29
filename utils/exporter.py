"""Safe, self-contained HTML report export."""

from __future__ import annotations

import html
import platform as stdlib_platform
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from core.paths import reports_directory
from platforms import PLATFORM_NAME
from utils.shopping import ensure_amazon_affiliate_tag


def _value(value, key: str, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _escape(value) -> str:
    return html.escape(str(value if value is not None else "Unavailable"), quote=True)


def _safe_url(value: str) -> str:
    tagged = ensure_amazon_affiliate_tag(value or "")
    parsed = urlparse(tagged)
    return tagged if parsed.scheme in ("http", "https") else ""


def _list(items, css_class: str = "") -> str:
    values = [item for item in (items or []) if item]
    if not values:
        return '<p class="muted">None reported.</p>'
    class_attr = f' class="{css_class}"' if css_class else ""
    return f"<ul{class_attr}>" + "".join(f"<li>{_escape(item)}</li>" for item in values) + "</ul>"


def _machine_summary(metrics: dict) -> str:
    rows = [
        ("Computer", metrics.get("machine") or stdlib_platform.node() or "Unavailable"),
        ("Operating system", metrics.get("os") or PLATFORM_NAME),
        ("Processor", metrics.get("cpu_name") or "Unavailable"),
        ("Memory", f"{metrics.get('ram_total_gb')} GB" if metrics.get("ram_total_gb") else "Unavailable"),
        ("Graphics", ", ".join(metrics.get("gpus") or []) or "Unavailable"),
        ("System storage", metrics.get("system_disk_type") or "Unavailable"),
        ("Motherboard / model", metrics.get("board_name") or "Unavailable"),
    ]
    return "".join(
        f'<div class="summary-item"><span>{_escape(label)}</span><strong>{_escape(value)}</strong></div>'
        for label, value in rows
    )


def _finding_html(finding) -> str:
    severity = _value(finding, "severity", "Info")
    return (
        '<div class="finding">'
        f'<span class="chip {_escape(severity).lower()}">{_escape(severity)}</span>'
        f'<strong>{_escape(_value(finding, "title", "Finding"))}</strong>'
        f'<p>{_escape(_value(finding, "detail", ""))}</p>'
        + (f'<p class="action">Action: {_escape(_value(finding, "action", ""))}</p>'
           if _value(finding, "action", "") else "")
        + "</div>"
    )


def _upgrade_html(upgrade) -> str:
    if not upgrade:
        return ""
    url = _safe_url(_value(upgrade, "url", ""))
    link = (
        f'<a href="{_escape(url)}" target="_blank" rel="noopener noreferrer">Open optional shopping search</a>'
        if url else ""
    )
    verify = _list(_value(upgrade, "verify_before_buying", []))
    return (
        '<section class="upgrade">'
        f'<div class="upgrade-head"><strong>{_escape(_value(upgrade, "priority", "Low"))} priority</strong>'
        f'<span>{_escape(_value(upgrade, "compatibility_confidence", "Low"))} compatibility confidence</span></div>'
        f'<h4>{_escape(_value(upgrade, "text", "Recommendation"))}</h4>'
        f'<p>{_escape(_value(upgrade, "why", ""))}</p>'
        '<div class="upgrade-grid">'
        f'<div><span>Current</span><strong>{_escape(_value(upgrade, "current_part", "Unavailable"))}</strong></div>'
        f'<div><span>Minimum target</span><strong>{_escape(_value(upgrade, "minimum_target", "Unavailable"))}</strong></div>'
        f'<div><span>Better target</span><strong>{_escape(_value(upgrade, "better_target", "Unavailable"))}</strong></div>'
        f'<div><span>DIY</span><strong>{_escape(_value(upgrade, "diy_friendly", "Varies"))}</strong></div>'
        '</div>'
        f'<p class="note">{_escape(_value(upgrade, "note", ""))}</p>'
        '<h5>Verify before buying</h5>' + verify + link + "</section>"
    )


def _category_html(category) -> str:
    scored = bool(_value(category, "scored", True))
    score = _value(category, "score", 0) if scored else "N/A"
    findings = _value(category, "findings", []) or []
    findings_html = "".join(_finding_html(finding) for finding in findings)
    return (
        '<article class="category">'
        '<div class="category-head">'
        f'<div class="score">{_escape(score)}</div>'
        f'<div><h3>{_escape(_value(category, "icon", ""))} {_escape(_value(category, "name", "Category"))}</h3>'
        f'<p>{_escape(_value(category, "stat", "Unavailable"))}</p></div>'
        f'<div class="status"><strong>{_escape(_value(category, "status", "Unavailable"))}</strong>'
        f'<span>Grade {_escape(_value(category, "grade", "N/A"))} · {_escape(_value(category, "confidence", "Unavailable"))} confidence</span></div>'
        '</div>'
        f'<p class="reason">{_escape(_value(category, "reason", ""))}</p>'
        + (f'<div class="unavailable">{_escape(_value(category, "unavailable_reason", ""))}</div>' if not scored else "")
        + findings_html
        + '<details><summary>Evidence and recommendations</summary><div class="detail-grid"><div><h5>Evidence</h5>'
        + _list(_value(category, "evidence", []))
        + '</div><div><h5>Recommended fixes</h5>'
        + _list(_value(category, "recommendations", []))
        + '</div></div></details>'
        + _upgrade_html(_value(category, "upgrade"))
        + "</article>"
    )


def _profile_html(key: str, result: dict, active: bool) -> str:
    actions = result.get("prioritized_actions", [])
    action_html = "".join(
        f'<li><span class="chip {_escape(item.get("severity", "Info")).lower()}">{_escape(item.get("severity", "Info"))}</span>'
        f'<strong>{_escape(item.get("category", ""))}: {_escape(item.get("title", ""))}</strong>'
        f'<p>{_escape(item.get("action", ""))}</p></li>'
        for item in actions
    ) or '<li class="muted">No priority fixes were identified by available checks.</li>'
    categories = "".join(_category_html(category) for category in result.get("categories", []))
    return (
        f'<section class="profile {"active" if active else ""}" id="profile-{_escape(key)}">'
        '<div class="hero">'
        f'<div class="overall">{_escape(result.get("overall", 0))}<small>/100</small></div>'
        f'<div><span>{_escape(result.get("profile", key))} profile</span>'
        f'<h2>{_escape(result.get("grade", "N/A"))} · {_escape(result.get("grade_label", "Unavailable"))}</h2>'
        f'<p>{_escape(result.get("blurb", ""))}</p></div></div>'
        '<section class="priorities"><h2>Prioritized fixes</h2><ol>' + action_html + "</ol></section>"
        '<div class="categories">' + categories + "</div></section>"
    )


def export_report(
    metrics: dict,
    all_results: dict,
    device_type: str,
    default_profile: str,
    *,
    scanned_at: str = "",
    output_dir: str | Path | None = None,
) -> str:
    """Generate an escaped, self-contained report and return its path."""
    generated = datetime.now().astimezone()
    scan_time = scanned_at or generated.isoformat(timespec="seconds")
    profiles = all_results.get(device_type, {})
    profile_keys = [key for key in ("Everyday", "Gaming", "Workstation") if key in profiles]
    if default_profile not in profile_keys and profile_keys:
        default_profile = profile_keys[0]

    tabs = "".join(
        f'<button type="button" data-profile="{_escape(key)}" class="tab {"active" if key == default_profile else ""}">{_escape(key)}</button>'
        for key in profile_keys
    )
    profile_sections = "".join(
        _profile_html(key, profiles[key], key == default_profile) for key in profile_keys
    )
    warnings = metrics.get("collection_warnings", [])
    warning_html = _list(
        [f"{warning.get('category', 'scan')}: {warning.get('message', 'Unavailable')}" for warning in warnings]
    )

    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ShmagStick Health Report</title>
<style>
:root{{--bg:#0b0d12;--panel:#151923;--panel2:#1b2030;--line:#2a3142;--text:#edf0f6;--muted:#99a3b7;--good:#2dd4a7;--warn:#f5c451;--high:#ff935c;--bad:#ff5c77;--accent:#6e8bff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 'Segoe UI',Arial,sans-serif}}main{{max-width:1200px;margin:auto;padding:32px}}header{{display:flex;justify-content:space-between;gap:24px;align-items:flex-end}}h1,h2,h3,h4,h5,p{{margin-top:0}}.eyebrow,.muted,.category-head p,.status span,.hero span{{color:var(--muted)}}.summary{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin:22px 0}}.summary-item,.hero,.priorities,.category,.disclaimer{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}}.summary-item span,.upgrade-grid span{{display:block;color:var(--muted);font-size:12px}}.tabs{{display:flex;gap:8px;margin:22px 0;flex-wrap:wrap}}button{{background:var(--panel);color:var(--muted);border:1px solid var(--line);padding:9px 16px;border-radius:9px;font-weight:700;cursor:pointer}}button.active{{color:white;border-color:var(--accent);background:#232d4a}}.profile{{display:none}}.profile.active{{display:block}}.hero{{display:flex;gap:24px;align-items:center}}.overall{{font-size:54px;font-weight:800;color:var(--good)}}.overall small{{font-size:14px;color:var(--muted)}}.priorities{{margin:16px 0}}.priorities li{{margin:10px 0}}.priorities p{{margin:4px 0 0;color:var(--muted)}}.categories{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px}}.category-head{{display:flex;gap:14px;align-items:center}}.category-head h3{{margin-bottom:2px}}.score{{width:56px;height:56px;border-radius:50%;background:#252b39;display:grid;place-items:center;font-size:20px;font-weight:800}}.status{{margin-left:auto;text-align:right}}.status span{{display:block;font-size:11px}}.reason{{font-weight:700;margin:12px 0}}.finding{{border-top:1px solid var(--line);padding:12px 0}}.finding p{{color:var(--muted);margin:5px 0 0}}.finding .action{{color:#c7d5f4;border-left:2px solid var(--accent);padding-left:8px}}.chip{{display:inline-block;padding:2px 7px;border-radius:5px;color:#0b0d12;font-size:10px;font-weight:800;margin-right:7px}}.critical{{background:var(--bad)}}.high{{background:var(--high)}}.medium{{background:var(--warn)}}.low{{background:#9aa3b5}}.info{{background:var(--accent)}}details{{margin-top:10px}}summary{{cursor:pointer;color:#cbd5e8}}.detail-grid,.upgrade-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.upgrade{{border-top:1px solid var(--line);margin-top:14px;padding-top:14px}}.upgrade-head{{display:flex;justify-content:space-between;color:var(--warn);font-size:12px}}.upgrade-grid div{{background:var(--panel2);padding:10px;border-radius:8px}}.note,.unavailable{{color:var(--muted)}}a{{color:var(--warn)}}.disclaimer{{margin-top:22px;color:var(--muted)}}
@media(max-width:700px){{main{{padding:16px}}header,.hero,.category-head{{align-items:flex-start;flex-direction:column}}.status{{margin-left:0;text-align:left}}.categories{{grid-template-columns:1fr}}.detail-grid,.upgrade-grid{{grid-template-columns:1fr}}}}
@media print{{body{{background:white;color:#111}}main{{max-width:none;padding:0}}.tabs{{display:none}}.profile{{display:block!important;break-before:page}}.profile:first-of-type{{break-before:auto}}.summary-item,.hero,.priorities,.category,.disclaimer{{background:white;border-color:#bbb;break-inside:avoid}}.muted,.category-head p,.status span,.hero span,.finding p,.note{{color:#444}}}}
</style></head><body><main>
<header><div><div class="eyebrow">READ-ONLY SYSTEM DIAGNOSTIC</div><h1>ShmagStick Health Report</h1></div><div class="eyebrow">Generated {_escape(generated.strftime('%Y-%m-%d %H:%M %Z'))}</div></header>
<div class="summary">{_machine_summary(metrics)}<div class="summary-item"><span>Device profile</span><strong>{_escape(device_type)}</strong></div><div class="summary-item"><span>Scan timestamp</span><strong>{_escape(scan_time)}</strong></div></div>
<nav class="tabs" aria-label="Scoring profiles">{tabs}</nav>{profile_sections}
<section class="disclaimer"><h2>Unavailable and limited checks</h2>{warning_html}<h2>Privacy and safety</h2><p>ShmagStick performs read-only diagnostics. It does not delete files, change settings, edit the registry, disable services, install software, or remove malware. It does not collect browsing history, passwords, documents, keys, or tokens. Process names and aggregate browser cache/extension counts may be included when available.</p><p>Scores and upgrade suggestions are diagnostic guidance, not a guarantee of compatibility. Verify the exact model, motherboard support list, form factor, firmware requirements, power, and physical clearances before purchasing hardware.</p></section>
</main><script>document.querySelectorAll('[data-profile]').forEach(function(button){{button.addEventListener('click',function(){{document.querySelectorAll('[data-profile]').forEach(function(item){{item.classList.toggle('active',item===button)}});document.querySelectorAll('.profile').forEach(function(section){{section.classList.toggle('active',section.id==='profile-'+button.dataset.profile)}})}})}});</script></body></html>"""

    destination = Path(output_dir) if output_dir else reports_directory()
    destination.mkdir(parents=True, exist_ok=True)
    hostname = re.sub(r"[^A-Za-z0-9._-]+", "_", stdlib_platform.node() or "host")
    filename = f"ShmagStick_{hostname}_{generated.strftime('%Y-%m-%d_%H%M%S')}.html"
    path = destination / filename
    path.write_text(document, encoding="utf-8")
    return str(path)
