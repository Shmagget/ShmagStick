# ShmagStick

ShmagStick is a portable, read-only system health checker for Windows, Linux, and macOS. It collects hardware and operating-system evidence, scores 13 diagnostic categories for Everyday, Gaming, or Workstation use, explains likely bottlenecks, and exports a self-contained HTML report.

## Safety first

ShmagStick does not delete files, change settings, edit the registry, disable services, install software, remove malware, or run repair commands. It does not collect browsing history, passwords, documents, keys, or tokens. Optional elevated access only exposes additional read-only evidence.

When a probe cannot run, the category is marked **Unavailable** or given lower confidence. Missing data is never treated as proof that a system is healthy.

## What it checks

1. CPU model, cores/threads, utilization, clock behavior, and likely bottlenecks.
2. RAM capacity, pressure, swap/commit use, slots where exposed, and top consumers.
3. System-drive capacity, free space, temporary data, and trash/recycle-bin estimates.
4. Boot-drive type, health indicators, TRIM, and safe saturation evidence where available.
5. GPU type, VRAM when reliable, driver age, errors, and profile suitability.
6. Startup/login items, uptime, and pending restart state.
7. User/third-party background services, tasks, and heavy processes.
8. Power profile, battery status/health, thermals, and throttling indicators.
9. Device, driver, firmware, and hardware-report warnings.
10. Operating-system update age and pending restart state.
11. Link speed, Wi-Fi signal, DNS presence, browser extensions, and cache size—never history.
12. Recent crashes, disk errors, hardware errors, kernel panics, and application crashes.
13. Native security, firewall, suspicious startup items, and other defensive indicators.

Exact coverage varies by operating system, hardware, permissions, and installed system utilities. See [PRIVACY.md](PRIVACY.md) for what is and is not collected, and [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if a scan will not run.

## Download and run

Pre-built executables for each operating system are published on the [**Releases page**](https://github.com/Shmagget/ShmagStick/releases/latest). Download the one file for your OS — no Python, no installation, nothing else to set up.

| Operating system | Download | How to run |
| --- | --- | --- |
| **Windows** 10/11 (64-bit) | `ShmagStick-Windows.exe` | Double-click it. |
| **macOS** (Apple Silicon, M1–M4) | `ShmagStick-macOS-AppleSilicon.zip` | Unzip, then right-click `ShmagStick.app` → **Open**. |
| **Linux** (64-bit) | `ShmagStick-Linux` | `chmod +x ShmagStick-Linux && ./ShmagStick-Linux` |

> Intel Macs (pre-2020) don't have a prebuilt download — run from source instead (see [Build your own executable](#build-your-own-executable)).

These are **unsigned** builds (code-signing certificates cost money), so your OS may warn you the first time you run them. This is expected for independent software:

- **Windows:** if SmartScreen says "Windows protected your PC," click **More info → Run anyway**.
- **macOS:** if Gatekeeper says the app "cannot be opened," right-click the app → **Open** and confirm. (Or run `xattr -dr com.apple.quarantine ShmagStick.app` once.)

Reports are saved to a `Reports/` folder created next to the executable; diagnostic logs go to `logs/`.

## Run from source

Most people should just download the prebuilt app above. To run from source instead, install the dependencies and start it:

```text
python -m pip install -r requirements.txt
python shmagstick.py --profile Everyday --device Auto
```

If Python 3.9+, PyQt6, and psutil are already installed, you can also launch with the helper scripts `Start-Windows.bat`, `Start-Linux.sh`, or `Start-macOS.command`. They never install anything.

## Build your own executable

To produce a standalone executable for the OS you are currently on:

```text
python -m pip install -r requirements-dev.txt
pyinstaller ShmagStick.spec --noconfirm --clean
```

The result appears in `dist/` (`ShmagStick.exe` on Windows, `ShmagStick` on Linux, `ShmagStick.app` on macOS). To build for all three operating systems at once, push a version tag and let GitHub Actions do it (see [`.github/workflows/build.yml`](.github/workflows/build.yml)).

## Scores

- **A (90–100):** Excellent
- **B (80–89):** Good
- **C (70–79):** Fair
- **D (55–69):** Poor
- **F (0–54):** Needs serious work
- **N/A:** Reliable evidence was unavailable

The overall score is 70% available-category weighted average plus 30% worst available category. A critical category caps the overall score at 59, so severe problems cannot be hidden by unrelated healthy checks. Unavailable categories are excluded rather than awarded healthy points.

## Upgrade guidance

Recommendations include the current part, minimum and better targets, priority, DIY practicality, compatibility confidence, and checks to perform before buying. Specific CPU recommendations are only produced when an offline motherboard compatibility profile matches; socket inference alone never authorizes a purchase recommendation. Laptop and Apple Silicon limitations are shown explicitly.

Shopping links are optional affiliate links and do not affect scoring. Generated Amazon links include the configured Amazon Associates tag `shmagstick-20`; Amazon determines whether a click qualifies for commission. No internet connection is required to scan.

## Reports and logs

Reports are written to a `Reports/` folder and rotating diagnostic logs to a `logs/` folder, both created next to the app the first time it runs.

## License

MIT. See [LICENSE](LICENSE).
