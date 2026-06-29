"""HTML report export — generates self-contained reports from scan results."""

from __future__ import annotations

import json
import os
import re
import platform as _stdlib_platform
from datetime import datetime

from platforms import PLATFORM_NAME


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ShmagStick Report</title>
<style>
  body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#0d0f14;color:#e8edf6;padding:26px}
  h1{margin:0}.sub{color:#8b95ab;font-size:13px}
  .tabs{margin:16px 0}
  .tb{display:inline-block;padding:7px 14px;margin-right:6px;border:1px solid #2a3145;border-radius:8px;cursor:pointer;color:#9aa6bd;font-weight:600}
  .tb.on{background:#2b3550;color:#fff}
  .hero{display:flex;gap:24px;align-items:center;background:#161b29;border:1px solid #2a3145;border-radius:16px;padding:20px;margin-bottom:18px}
  .big{font-size:44px;font-weight:bold}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
  .card{background:#1b2030;border:1px solid #2a3145;border-radius:14px;padding:16px}
  .cn{font-size:16px;font-weight:bold}
  .cs{color:#8b95ab;font-size:12px;margin:3px 0 10px}
  .f{border-top:1px solid #2a3145;padding:9px 0;font-size:13px}
  .chip{font-size:10px;font-weight:bold;padding:2px 6px;border-radius:5px;color:#0d0f14;margin-right:7px}
  .d{color:#8b95ab;font-size:12px;margin-top:3px}
  .a{color:#bfd4ff;font-size:12px;border-left:2px solid #4ea1ff;padding-left:8px;margin-top:5px}
  .gnum{display:inline-block;width:46px;height:46px;line-height:46px;text-align:center;border-radius:50%;font-weight:bold;margin-right:10px}
  .up{border-top:1px solid #2a3145;margin-top:10px;padding-top:8px}
  .uph{font-size:10px;font-weight:bold;letter-spacing:1px;color:#ffc857}
  .ut{font-size:13px;margin-top:4px}
  a{color:#ffc857;font-size:13px;text-decoration:none}a:hover{text-decoration:underline}
</style>
</head>
<body>
<h1>ShmagStick Report</h1>
<div class="sub">__MACHINE__ &middot; __OS__ &middot; __DEVICE__ &middot; __DATE__</div>
<div class="tabs" id="tabs"></div>
<div class="hero"><div><div class="big" id="ov"></div><div class="sub">/100</div></div>
<div><div class="sub" id="pn"></div>
<div style="font-size:22px"><b id="gl"></b> <span id="gw" class="sub"></span></div>
<div class="sub" id="bl" style="max-width:560px;margin-top:6px"></div></div></div>
<div class="grid" id="grid"></div>
<script>
const D=__DATA__;
const SEV={Critical:'#ff5470',High:'#ff8a3d',Medium:'#f7c948',Low:'#7a8499',Info:'#4ea1ff'};
function col(s){return s>=80?'#22d39a':s>=50?'#f7c948':s>=30?'#ff8a3d':'#ff5470'}
function arr(x){return Array.isArray(x)?x:(x?[x]:[])}
function R(k){
  const d=D.profiles[k];
  document.querySelectorAll('.tb').forEach(t=>t.className='tb'+(t.dataset.k===k?' on':''));
  ov.textContent=d.overall;ov.style.color=col(d.overall);
  pn.textContent=d.profile.toUpperCase()+' PROFILE';
  gl.textContent=d.grade;gl.style.color=col(d.overall);
  gw.textContent='- '+d.gradeLabel;bl.textContent=d.blurb;
  grid.innerHTML=arr(d.categories).map(c=>{
    const real=arr(c.findings).filter(f=>f.severity!=='Info');
    const fs=real.length?real.map(f=>`<div class="f"><span class="chip" style="background:${SEV[f.severity]}">${f.severity.toUpperCase()}</span><b>${f.title}</b>${f.detail?`<div class="d">${f.detail}</div>`:''}${f.action?`<div class="a">${f.action}</div>`:''}</div>`).join(''):'<div class="f" style="color:#22d39a">No issues found!</div>';
    const up=c.upgrade?`<div class="up"><div class="uph">&#128161; SUGGESTED UPGRADE</div><div class="ut">${c.upgrade.text}</div>${c.upgrade.url?`<a href="${c.upgrade.url}" target="_blank" rel="noopener">View recommended upgrade &#8594;</a>`:''}${c.upgrade.note?`<div class="d">${c.upgrade.note}</div>`:''}</div>`:'';
    return `<div class="card"><div><span class="gnum" style="background:${col(c.score)}22;color:${col(c.score)}">${c.score}</span><span class="cn">${c.icon} ${c.name}</span></div><div class="cs">${c.stat}</div>${fs}${up}</div>`}).join('');
}
const t=document.getElementById('tabs');
['Everyday','Gaming','Workstation'].forEach(k=>{const b=document.createElement('span');b.className='tb';b.dataset.k=k;b.textContent=k;b.onclick=()=>R(k);t.appendChild(b)});
R(D.defaultProfile||'Everyday');
</script>
</body>
</html>
"""


def export_report(metrics: dict, all_results: dict, device_type: str, default_profile: str) -> str:
    """Generate a self-contained HTML report and return the file path.

    Args:
        metrics: Raw collected metrics dict.
        all_results: {device: {profile: result_dict}} from scoring engine.
        device_type: "Desktop" or "Laptop".
        default_profile: Key of the profile to show first.

    Returns:
        Path to the written HTML file.
    """
    machine = metrics.get("machine", "Unknown")
    os_str = metrics.get("os", PLATFORM_NAME)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build data payload
    payload = {
        "generated": now,
        "machine": machine,
        "os": os_str,
        "device": device_type,
        "defaultProfile": default_profile,
        "profiles": all_results.get(device_type, {}),
    }

    import json
    data_json = json.dumps(payload, ensure_ascii=False, default=str)

    html = (
        _HTML_TEMPLATE
        .replace("__DATA__", data_json)
        .replace("__MACHINE__", machine)
        .replace("__OS__", os_str)
        .replace("__DEVICE__", device_type)
        .replace("__DATE__", now)
    )

    # Write to Reports/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    reports_dir = os.path.join(base_dir, "Reports")
    os.makedirs(reports_dir, exist_ok=True)

    hostname = re.sub(r"[^A-Za-z0-9._-]+", "_", _stdlib_platform.node() or "host")
    safe_time = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"ShmagStick_{hostname}_{safe_time}.html"
    path = os.path.join(reports_dir, filename)

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)

    return path
