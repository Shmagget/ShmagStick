"""Main application window — QMainWindow with full dark-themed UI."""

from __future__ import annotations

import datetime
import os
import platform as _platform_mod
import sys

from PyQt6.QtCore import QThread, Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from platforms import get_collector, PLATFORM_NAME
from scoring.engine import evaluate
from gui.styles import STYLESHEET
from gui.gauge_widget import GaugeWidget
from gui.collapsible_card import CollapsibleSection
from gui.scan_worker import ScanWorker
from core.logging_config import configure_logging, safe_path
from core.scanner import ScanService


class MainWindow(QMainWindow):
    def __init__(self, initial_profile: str = "Everyday", device_mode: str = "Auto"):
        super().__init__()
        self.setWindowTitle("ShmagStick")
        self.setMinimumSize(960, 720)

        self.collector = get_collector()
        self.scan_service = ScanService(lambda: self.collector)
        self.current_profile = initial_profile
        self.device_mode = device_mode
        self.device_type = "Desktop"
        self.metrics: dict = {}
        self.results: dict = {}
        self.is_scanning = False
        self._deep_running = False
        self.scan_thread = None
        self.scan_worker = None
        self.scanned_at = ""
        self._sections = []
        self.deep_sections = []
        self._close_when_scan_finishes = False
        self.logger = configure_logging().getChild("gui")

        self._build_ui()
        self.setStyleSheet(STYLESHEET)
        QTimer.singleShot(100, self._initial_scan)

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(26, 24, 26, 18)
        outer.setSpacing(0)

        # --- Top bar ---
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)

        left_stack = QVBoxLayout()
        left_stack.setContentsMargins(0, 0, 0, 0)
        left_stack.setSpacing(1)
        lbl_sys = QLabel("SYSTEM HEALTH SCANNER")
        lbl_sys.setStyleSheet("color: #8B94A7; font-size: 11px; font-weight: bold;")
        lbl_title = QLabel("ShmagStick")
        lbl_title.setStyleSheet("font-size: 27px; font-weight: bold; margin-top: 2px;")
        left_stack.addWidget(lbl_sys)
        left_stack.addWidget(lbl_title)

        # Subtitle lives on its own full-width row (below the top bar) so the
        # machine/OS/admin line never clips against the tabs.
        self.lbl_subtitle = QLabel("")
        self.lbl_subtitle.setObjectName("subtitle")
        self.lbl_subtitle.setWordWrap(True)
        self.lbl_subtitle.setStyleSheet(
            "QLabel#subtitle { color: #8B94A7; font-size: 12px; }"
        )

        top.addLayout(left_stack)
        top.addStretch()

        self.btn_everyday = self._tab_btn("Everyday")
        self.btn_gaming = self._tab_btn("Gaming")
        self.btn_workstation = self._tab_btn("Workstation")
        top.addWidget(self.btn_everyday)
        top.addWidget(self.btn_gaming)
        top.addWidget(self.btn_workstation)

        spacer = QWidget()
        spacer.setFixedWidth(16)
        top.addWidget(spacer)

        self.btn_rescan = self._action_btn("Rescan")
        self.btn_deep = self._action_btn("Deep scan")
        self.btn_deep.setToolTip(
            "Slower, read-only deep scan: finds the largest files/space hogs and "
            "surfaces threat indicators and your OS security history. Never deletes anything."
        )
        self.btn_export = self._action_btn("Export report")
        top.addWidget(self.btn_rescan)
        top.addWidget(self.btn_deep)
        top.addWidget(self.btn_export)
        outer.addLayout(top)

        outer.addSpacing(8)
        outer.addWidget(self.lbl_subtitle)
        outer.addSpacing(16)

        # --- Hero section ---
        hero = QWidget()
        hero.setObjectName("heroSection")
        hero.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(28, 22, 22, 22)
        hero_layout.setSpacing(0)

        hero_left = QHBoxLayout()
        hero_left.setSpacing(26)

        self.hero_gauge = GaugeWidget(size=148, thickness=12)
        hero_left.addWidget(self.hero_gauge, 0, Qt.AlignmentFlag.AlignVCenter)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(5)

        self.lbl_pname = QLabel("")
        self.lbl_pname.setStyleSheet("font-size: 12px; color: #8B94A7; font-weight: bold;")
        info_layout.addWidget(self.lbl_pname)

        grade_row = QHBoxLayout()
        grade_row.setContentsMargins(0, 4, 0, 0)
        grade_row.setSpacing(0)
        grade_prefix = QLabel("Overall grade  ")
        grade_prefix.setStyleSheet("font-size: 14px; color: #8B94A7;")
        grade_row.addWidget(grade_prefix)

        self.lbl_grade = QLabel("-")
        self.lbl_grade.setStyleSheet("font-size: 33px; font-weight: bold;")
        grade_row.addWidget(self.lbl_grade)

        self.lbl_grade_label = QLabel("")
        self.lbl_grade_label.setObjectName("gradeLabel")
        self.lbl_grade_label.setStyleSheet(
            "QLabel#gradeLabel { color: #8B94A7; font-size: 14px; margin-left: 12px; }"
        )
        grade_row.addWidget(self.lbl_grade_label)
        grade_row.addStretch()
        info_layout.addLayout(grade_row)

        self.lbl_blurb = QLabel("")
        self.lbl_blurb.setObjectName("blurb")
        self.lbl_blurb.setWordWrap(True)
        self.lbl_blurb.setMaximumWidth(520)
        self.lbl_blurb.setStyleSheet(
            "QLabel#blurb { color: #9AA3B5; font-size: 13px; margin-top: 7px; }"
        )
        info_layout.addWidget(self.lbl_blurb)

        self.lbl_scan_status = QLabel("Ready to scan")
        self.lbl_scan_status.setStyleSheet("color: #6E8BFF; font-size: 11px; margin-top: 6px;")
        info_layout.addWidget(self.lbl_scan_status)
        self.scan_progress = QProgressBar()
        self.scan_progress.setRange(0, 100)
        self.scan_progress.setTextVisible(False)
        self.scan_progress.setFixedHeight(5)
        self.scan_progress.hide()
        info_layout.addWidget(self.scan_progress)

        hero_left.addLayout(info_layout)
        hero_layout.addLayout(hero_left, 0)
        hero_layout.addStretch()

        # Device-type panel (bordered control block on the right of the hero)
        dev_panel = QWidget()
        dev_panel.setObjectName("devicePanel")
        dev_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        dev_panel.setFixedWidth(176)
        dev_layout = QVBoxLayout(dev_panel)
        dev_layout.setContentsMargins(16, 14, 16, 16)
        dev_layout.setSpacing(0)
        dev_label = QLabel("DEVICE TYPE")
        dev_label.setStyleSheet(
            "color: #8B94A7; font-size: 10px; font-weight: bold; margin-bottom: 9px;"
        )
        dev_layout.addWidget(dev_label)

        self.btn_auto = self._tab_btn("Auto")
        self.btn_desktop = self._tab_btn("Desktop")
        self.btn_laptop = self._tab_btn("Laptop")
        for button in (self.btn_auto, self.btn_desktop, self.btn_laptop):
            button.setFixedWidth(144)

        dev_layout.addWidget(self.btn_auto)
        dev_layout.addSpacing(8)
        dev_layout.addWidget(self.btn_desktop)
        dev_layout.addSpacing(8)
        dev_layout.addWidget(self.btn_laptop)
        hero_layout.addWidget(dev_panel, 0, Qt.AlignmentFlag.AlignVCenter)

        outer.addWidget(hero)

        # Soft elevation on the hero only (cards stay flat for performance).
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(34)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 7)
        hero.setGraphicsEffect(shadow)

        # --- Technician summary ---
        summary = QWidget()
        summary.setObjectName("summaryPanel")
        summary.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(18, 14, 18, 14)
        summary_layout.setSpacing(24)
        self.lbl_actions = QLabel("Priority actions will appear after the scan.")
        self.lbl_actions.setWordWrap(True)
        self.lbl_actions.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_actions.setStyleSheet("color: #C9D1E3; font-size: 12px;")
        self.lbl_upgrades = QLabel("Upgrade guidance will appear after the scan.")
        self.lbl_upgrades.setWordWrap(True)
        self.lbl_upgrades.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_upgrades.setStyleSheet("color: #C9D1E3; font-size: 12px;")
        summary_layout.addWidget(self.lbl_actions, 1)
        summary_layout.addWidget(self.lbl_upgrades, 1)
        outer.addSpacing(12)
        outer.addWidget(summary)

        # --- Section toolbar (expand / collapse all) ---
        sec_bar = QHBoxLayout()
        sec_bar.setContentsMargins(2, 0, 2, 0)
        sec_title = QLabel("CATEGORY DETAILS")
        sec_title.setStyleSheet("color: #8B94A7; font-size: 11px; font-weight: bold;")
        sec_bar.addWidget(sec_title)
        sec_bar.addStretch()
        self.btn_expand_all = self._action_btn("Expand all")
        self.btn_collapse_all = self._action_btn("Collapse all")
        sec_bar.addWidget(self.btn_expand_all)
        sec_bar.addWidget(self.btn_collapse_all)
        outer.addSpacing(14)
        outer.addLayout(sec_bar)
        outer.addSpacing(8)

        # --- Sections (collapsible accordion) ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_content.setObjectName("scrollContent")
        scroll_content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.sections_layout = QVBoxLayout(scroll_content)
        self.sections_layout.setContentsMargins(0, 2, 8, 0)
        self.sections_layout.setSpacing(9)
        self.sections_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(scroll_content)
        scroll.viewport().setStyleSheet("background: transparent;")
        outer.addWidget(scroll, 1)

        # --- Footer ---
        footer_sep = QWidget()
        footer_sep.setObjectName("footerSeparator")
        footer_sep.setFixedHeight(1)
        footer_sep.setStyleSheet("QWidget#footerSeparator { background: #1F2430; }")
        outer.addSpacing(10)
        outer.addWidget(footer_sep)
        outer.addSpacing(8)

        footer = QLabel(
            "\U0001F4A1 Suggested-upgrade links are affiliate links - "
            "purchases may earn the developer a small commission at no extra cost to you."
        )
        footer.setObjectName("footer")
        footer.setStyleSheet(
            "QLabel#footer { color: #8B94A7; font-size: 11px; }"
        )
        outer.addWidget(footer)

        # --- Wire events ---
        self.btn_everyday.clicked.connect(lambda: self._switch_profile("Everyday"))
        self.btn_gaming.clicked.connect(lambda: self._switch_profile("Gaming"))
        self.btn_workstation.clicked.connect(lambda: self._switch_profile("Workstation"))
        self.btn_auto.clicked.connect(lambda: self._switch_device("Auto"))
        self.btn_desktop.clicked.connect(lambda: self._switch_device("Desktop"))
        self.btn_laptop.clicked.connect(lambda: self._switch_device("Laptop"))
        self.btn_rescan.clicked.connect(self._rescan)
        self.btn_deep.clicked.connect(self._deep_scan)
        self.btn_export.clicked.connect(self._export)
        self.btn_expand_all.clicked.connect(lambda: self._set_all_expanded(True))
        self.btn_collapse_all.clicked.connect(lambda: self._set_all_expanded(False))

    def _tab_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("role", "tab")
        btn.setProperty("active", "false")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def _action_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("role", "action")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    # ---- Scan ----
    def _initial_scan(self):
        self._do_scan()

    def _rescan(self):
        self._do_scan(deep=False)

    def _deep_scan(self):
        self._do_scan(deep=True)

    def _do_scan(self, deep: bool = False):
        if self.is_scanning:
            return
        self.is_scanning = True
        self._deep_running = deep

        active = self.btn_deep if deep else self.btn_rescan
        active.setText("Deep scanning..." if deep else "Scanning...")
        active.setProperty("state", "scanning")
        active.style().unpolish(active)
        active.style().polish(active)
        self.btn_rescan.setEnabled(False)
        self.btn_deep.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.scan_progress.setValue(0)
        self.scan_progress.show()
        self.lbl_scan_status.setText(
            "Preparing deep read-only checks (this can take a minute)..." if deep
            else "Preparing read-only checks..."
        )

        self.scan_thread = QThread(self)
        self.scan_worker = ScanWorker(self.scan_service, deep=deep)
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.progress.connect(self._scan_progress)
        self.scan_worker.finished.connect(self._scan_complete)
        self.scan_worker.failed.connect(self._scan_failed)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.failed.connect(self.scan_thread.quit)
        self.scan_thread.finished.connect(self.scan_worker.deleteLater)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        self.scan_thread.finished.connect(self._scan_thread_finished)
        self.scan_thread.start()

    def _scan_progress(self, percent: int, label: str):
        self.scan_progress.setValue(percent)
        self.lbl_scan_status.setText(label)

    def _scan_complete(self, bundle):
        self.metrics = bundle.metrics
        self.results = bundle.results
        self.deep_sections = list(getattr(bundle, "deep_sections", []) or [])
        self.scanned_at = bundle.scanned_at
        detected = "Laptop" if self.metrics.get("is_laptop") else "Desktop"
        self.device_type = detected if self.device_mode == "Auto" else self.device_mode
        warning_count = len(self.metrics.get("collection_warnings", []))
        deep_note = " · deep scan results added below" if self.deep_sections else ""
        self.lbl_scan_status.setText(
            f"Scan complete · {warning_count} limited check{'s' if warning_count != 1 else ''}{deep_note}"
        )
        self._finish_scan_ui()
        self._update_subtitle()
        self._render()

    def _scan_failed(self, message: str):
        self.logger.error("Scan failed: %s", safe_path(message))
        self.metrics = {"_error": message}
        self.results = {}
        self.deep_sections = []
        self._clear_sections()
        self.hero_gauge.setUnavailable()
        self.lbl_grade.setText("N/A")
        self.lbl_grade.setStyleSheet("font-size: 32px; font-weight: bold; color: #8B94A7;")
        self.lbl_grade_label.setText("- Scan unavailable")
        self.lbl_pname.setText("NO RELIABLE RESULT")
        self.lbl_blurb.setText("The previous result was cleared because the rescan did not complete reliably.")
        self.lbl_scan_status.setText("Scan unavailable — see logs for details")
        self.lbl_actions.setText("PRIORITY ACTIONS\nThe scan could not be completed. No scores were generated.")
        self.lbl_upgrades.setText("UPGRADE GUIDANCE\nUnavailable until a reliable scan completes.")
        self._finish_scan_ui()

    def _finish_scan_ui(self):
        self.is_scanning = False
        self._deep_running = False
        for button, text in ((self.btn_rescan, "Rescan"), (self.btn_deep, "Deep scan")):
            button.setText(text)
            button.setProperty("state", "")
            button.style().unpolish(button)
            button.style().polish(button)
            button.setEnabled(True)
        self.btn_export.setEnabled(bool(self.results))
        self.scan_progress.hide()

    def _scan_thread_finished(self):
        self.scan_worker = None
        self.scan_thread = None
        if self._close_when_scan_finishes:
            self._close_when_scan_finishes = False
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event):
        if self.scan_thread is not None and self.scan_thread.isRunning():
            self._close_when_scan_finishes = True
            self.lbl_scan_status.setText("Finishing the read-only scan before closing safely...")
            self.hide()
            event.ignore()
            return
        super().closeEvent(event)

    def _update_subtitle(self):
        machine = self.metrics.get("machine", self.collector.__class__.__name__)
        os_str = self.metrics.get("os", PLATFORM_NAME)
        if _platform_mod.system() == "Windows":
            is_admin = _is_windows_admin()
        elif hasattr(os, "geteuid"):
            is_admin = os.geteuid() == 0
        else:
            is_admin = True
        admin_note = "" if is_admin else "  ·  run as admin for a deeper scan"
        self.lbl_subtitle.setText(
            f"{machine}  ·  {os_str}  ·  device: {self.device_mode} ({self.device_type}){admin_note}"
        )

    # ---- Render ----
    def _switch_profile(self, key: str):
        self.current_profile = key
        self._update_tab_styles()
        self._render()

    def _switch_device(self, dev: str):
        self.device_mode = dev
        if dev == "Auto":
            self.device_type = "Laptop" if self.metrics.get("is_laptop") else "Desktop"
        else:
            self.device_type = dev
        self._update_device_tab_styles()
        self._render()

    def _update_tab_styles(self):
        for btn, key in [
            (self.btn_everyday, "Everyday"),
            (self.btn_gaming, "Gaming"),
            (self.btn_workstation, "Workstation"),
        ]:
            active = key == self.current_profile
            btn.setProperty("active", "true" if active else "false")
            btn.setChecked(active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _update_device_tab_styles(self):
        for btn, key in [
            (self.btn_auto, "Auto"),
            (self.btn_desktop, "Desktop"),
            (self.btn_laptop, "Laptop"),
        ]:
            active = key == self.device_mode
            btn.setProperty("active", "true" if active else "false")
            btn.setChecked(active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _render(self):
        if not self.results:
            return

        data = self.results.get(self.device_type, {}).get(self.current_profile)
        if not data:
            return

        self._update_tab_styles()
        self._update_device_tab_styles()

        self.hero_gauge.setScore(data["overall"], animate=True)

        from gui.gauge_widget import _score_to_color as stc
        color = stc(data["overall"])
        self.lbl_grade.setText(data["grade"])
        self.lbl_grade.setStyleSheet(
            f"font-size: 32px; font-weight: bold; color: {color};"
        )
        self.lbl_grade_label.setText(f"- {data['grade_label']}")
        self.lbl_pname.setText(f"{data['profile'].upper()} PROFILE")
        self.lbl_blurb.setText(data["blurb"])
        self._render_summary(data)

        self._clear_sections()

        cats = data.get("categories", [])
        for cat in cats:
            section = CollapsibleSection(cat, expanded=False)
            self._sections.append(section)
            self.sections_layout.addWidget(section)

        # Deep-scan sections (if a deep scan has been run) appear below the
        # standard categories and start expanded so results are immediately visible.
        if self.deep_sections:
            header = QLabel("\U0001F52C  DEEP SCAN RESULTS")
            header.setObjectName("deepHeader")
            header.setStyleSheet(
                "QLabel#deepHeader { color: #B9C6E8; font-size: 12px; font-weight: bold;"
                " margin-top: 10px; margin-bottom: 0px; }"
            )
            self.sections_layout.addWidget(header)
            for cat in self.deep_sections:
                section = CollapsibleSection(cat, expanded=True)
                self._sections.append(section)
                self.sections_layout.addWidget(section)

    def _render_summary(self, data: dict):
        actions = data.get("prioritized_actions", [])[:4]
        action_lines = ["PRIORITY ACTIONS"]
        action_lines.extend(
            f"{index}. [{item['severity']}] {item['category']}: {item['title']} — {item['action']}"
            for index, item in enumerate(actions, 1)
        )
        if not actions:
            action_lines.append("No urgent actions were identified by available checks.")
        self.lbl_actions.setText("\n".join(action_lines))

        upgrades = [
            category.upgrade for category in data.get("categories", [])
            if category.upgrade and category.upgrade.kind in ("buy", "advisory")
        ]
        priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        upgrades.sort(key=lambda upgrade: priority_order.get(upgrade.priority, 4))
        upgrades = upgrades[:4]
        upgrade_lines = ["UPGRADE GUIDANCE"]
        upgrade_lines.extend(
            f"{upgrade.priority}: {upgrade.text} (confidence: {upgrade.compatibility_confidence})"
            for upgrade in upgrades
        )
        if not upgrades:
            upgrade_lines.append("No hardware purchase is currently justified by the evidence.")
        self.lbl_upgrades.setText("\n".join(upgrade_lines))

    def _clear_sections(self):
        while self.sections_layout.count():
            item = self.sections_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._sections = []

    def _set_all_expanded(self, expanded: bool):
        for section in self._sections:
            if isinstance(section, CollapsibleSection):
                section.set_expanded(expanded)

    # ---- Export ----
    def _export(self):
        if not self.results:
            return

        from utils.exporter import export_report
        try:
            path = export_report(
                self.metrics,
                self.results,
                self.device_type,
                self.current_profile,
                scanned_at=self.scanned_at,
            )
            self.lbl_scan_status.setText(f"Report saved: {os.path.basename(path)}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except Exception as exc:
            self.logger.error("Report export failed: %s", type(exc).__name__)
            self.lbl_scan_status.setText(f"Report export failed: {type(exc).__name__}")


def _is_windows_admin() -> bool:
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False
