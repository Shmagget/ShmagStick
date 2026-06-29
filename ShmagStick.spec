# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for ShmagStick — single source of truth for all platforms.

Build locally or in CI with:

    pyinstaller ShmagStick.spec

Produces:
  * Windows : dist/ShmagStick.exe          (single file, double-click to run)
  * Linux   : dist/ShmagStick              (single file, chmod +x then run)
  * macOS   : dist/ShmagStick.app          (app bundle, double-click to run)
"""

import sys

# Platform collectors are imported dynamically at runtime, so PyInstaller's
# static analysis cannot see them. List them explicitly.
hidden_imports = [
    "platforms.windows",
    "platforms.linux",
    "platforms.macos",
]
if sys.platform == "win32":
    # Windows-only hardware probes use COM/WMI, also imported dynamically.
    hidden_imports += ["wmi", "comtypes.client"]

# UPX compression is intentionally disabled: it slows startup slightly and is a
# common trigger for antivirus / SmartScreen false positives on unsigned builds.
USE_UPX = False

# macOS GUI apps are distributed as .app bundles (one-dir under the hood);
# Windows and Linux ship as a single self-contained executable.
ONE_FILE = sys.platform != "darwin"

# Branding. The window / taskbar / dock icon is bundled as data and loaded at
# runtime via core.paths.resource_path; the executable/bundle icon is set per
# platform from the format that OS understands.
app_datas = [("assets/icon.png", "assets")]
if sys.platform == "win32":
    app_icon = "assets/icon.ico"
elif sys.platform == "darwin":
    app_icon = "assets/icon.icns"
else:
    app_icon = None  # Linux has no per-file icon; the runtime window icon covers it.


a = Analysis(
    ["shmagstick.py"],
    pathex=[],
    binaries=[],
    datas=app_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)


if ONE_FILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="ShmagStick",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=USE_UPX,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=app_icon,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="ShmagStick",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=USE_UPX,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=app_icon,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=USE_UPX,
        upx_exclude=[],
        name="ShmagStick",
    )
    app = BUNDLE(
        coll,
        name="ShmagStick.app",
        icon="assets/icon.icns",
        bundle_identifier="com.shmagstick.app",
        info_plist={
            "CFBundleName": "ShmagStick",
            "CFBundleDisplayName": "ShmagStick",
            "NSHighResolutionCapable": True,
            # Read-only system scanner; no network entitlement needed.
            "LSMinimumSystemVersion": "11.0",
        },
    )
