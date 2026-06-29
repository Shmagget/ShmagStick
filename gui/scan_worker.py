"""Background Qt worker for responsive system scans."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


class ScanWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, scan_service, deep: bool = False):
        super().__init__()
        self.scan_service = scan_service
        self.deep = deep

    @pyqtSlot()
    def run(self) -> None:
        try:
            bundle = self.scan_service.scan(
                lambda percent, label: self.progress.emit(percent, label),
                deep=self.deep,
            )
            self.finished.emit(bundle)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
