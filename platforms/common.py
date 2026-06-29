"""Small cross-platform helpers used by read-only collectors."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import psutil


@dataclass(frozen=True)
class CommandResult:
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.error


def run_command(command: list[str], timeout: int = 10) -> CommandResult:
    """Run a fixed argument list without a shell or host mutation."""
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(completed.stdout, completed.stderr, completed.returncode)
    except FileNotFoundError:
        return CommandResult(error="command not installed")
    except PermissionError:
        return CommandResult(error="permission denied")
    except subprocess.TimeoutExpired:
        return CommandResult(error="command timed out")
    except OSError as exc:
        return CommandResult(error=type(exc).__name__)


def folder_size_gb(path: str | Path, depth: int = 2, max_entries: int = 100_000) -> float:
    """Estimate folder size without following links or reading file contents."""
    root_path = Path(path).expanduser()
    if not root_path.is_dir():
        return 0.0
    total = 0
    visited = 0
    try:
        for root, dirs, files in os.walk(root_path, followlinks=False):
            root_obj = Path(root)
            try:
                level = len(root_obj.relative_to(root_path).parts)
            except ValueError:
                continue
            if level >= depth:
                dirs[:] = []
            for filename in files:
                visited += 1
                if visited > max_entries:
                    return round(total / (1024 ** 3), 2)
                try:
                    file_path = root_obj / filename
                    if not file_path.is_symlink():
                        total += file_path.stat().st_size
                except OSError:
                    continue
    except OSError:
        return round(total / (1024 ** 3), 2)
    return round(total / (1024 ** 3), 2)


def process_snapshot(limit: int = 5) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    """Return current CPU-percent and resident-memory process summaries."""
    processes: list[psutil.Process] = []
    for process in psutil.process_iter(["name", "memory_info"]):
        try:
            process.cpu_percent(None)
            processes.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    time.sleep(0.12)

    cpu_rows: list[tuple[str, float]] = []
    memory_rows: list[tuple[str, float]] = []
    for process in processes:
        try:
            name = process.info.get("name") or f"PID {process.pid}"
            cpu_rows.append((name, round(process.cpu_percent(None), 1)))
            memory_info = process.info.get("memory_info")
            memory_gb = (memory_info.rss / (1024 ** 3)) if memory_info else 0.0
            memory_rows.append((name, round(memory_gb, 2)))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    cpu_rows.sort(key=lambda row: row[1], reverse=True)
    memory_rows.sort(key=lambda row: row[1], reverse=True)
    return cpu_rows[:limit], memory_rows[:limit]


def average_cpu_load(samples: int = 3, interval: float = 0.15) -> int:
    readings = [psutil.cpu_percent(interval=interval) for _ in range(samples)]
    return round(sum(readings) / len(readings)) if readings else 0
