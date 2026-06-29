# Troubleshooting

## The launcher says no build or Python environment was found

Download the prebuilt app for your operating system from the [Releases page](https://github.com/Shmagget/ShmagStick/releases/latest), or install Python 3.9+ with PyQt6 and psutil (`python -m pip install -r requirements.txt`) and run from source. Launchers do not download or install dependencies.

## Linux displays a Qt/XCB error

Install the Qt/XCB runtime packages for the distro and launch from a graphical desktop session with `DISPLAY` or Wayland configured.

## macOS blocks the app

Unsigned local builds may be quarantined. Prefer a signed/notarized release. For an authorized local build, use Finder's Open context action and review the security prompt; do not globally disable Gatekeeper.

## Some categories say Unavailable

This is intentional when hardware, permissions, an optional command, or the operating system does not expose reliable evidence. Review the reason and `logs/shmagstick.log`. Optional elevation may help, but do not elevate merely to remove an N/A label.

## SMART or temperature data is missing

Many USB bridges, RAID controllers, laptops, virtual machines, and vendor firmware hide these values. Linux may require `smartctl`; Windows ACPI thermal zones are often unavailable; macOS generally does not expose temperatures through supported command-line tools.

## The report cannot be saved

Ensure the folder the app runs from is writable and not write-protected. Reports default to `Reports/` beside the app; logs default to `logs/`.

## The scan appears slow

Event-log, system-profiler, browser-cache-size, and storage-health checks can take several seconds. The GUI remains responsive and shows the active category. A timed-out probe becomes a warning instead of hanging the scan.
