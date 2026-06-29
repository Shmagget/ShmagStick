"""Main application window — QMainWindow with full dark-themed UI."""

from __future__ import annotations

import datetime
import os
import platform as _platform_mod
import sys

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from platforms import get_collector, PLATFORM_NAME
from scoring.engine import evaluate
from gui.styles import STYLESHEET
from gui.gauge_widget import GaugeWidget
from gui.card_widget import CategoryCard


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ShmagStick")
        self.setMinimumSize(1140, 820)

        self.collector = get_collector()
        self.current_profile = "Everyday"
        self.device_type = "Desktop"
        self.metrics: dict = {}
        self.results: dict = {}
        self.is_scanning = False

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
        self.btn_export = self._action_btn("Export report")
        top.addWidget(self.btn_rescan)
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

        self.btn_desktop = self._tab_btn("Desktop")
        self.btn_laptop = self._tab_btn("Laptop")
        self.btn_desktop.setFixedWidth(144)
        self.btn_laptop.setFixedWidth(144)

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

        # --- Cards area ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_content.setObjectName("scrollContent")
        scroll_content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.cols_layout = QHBoxLayout(scroll_content)
        self.cols_layout.setContentsMargins(0, 18, 0, 0)
        self.cols_layout.setSpacing(16)
        self.cols_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.col0 = QVBoxLayout()
        self.col1 = QVBoxLayout()
        self.col2 = QVBoxLayout()
        self.card_columns = (self.col0, self.col1, self.col2)
        for col in self.card_columns:
            col.setAlignment(Qt.AlignmentFlag.AlignTop)
            col.setSpacing(16)

        self.cols_layout.addLayout(self.col0)
        self.cols_layout.addLayout(self.col1)
        self.cols_layout.addLayout(self.col2)
        self.cols_layout.addStretch(1)

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
            "QLabel#footer { color: #5E6678; font-size: 11px; }"
        )
        outer.addWidget(footer)

        # --- Wire events ---
        self.btn_everyday.clicked.connect(lambda: self._switch_profile("Everyday"))
        self.btn_gaming.clicked.connect(lambda: self._switch_profile("Gaming"))
        self.btn_workstation.clicked.connect(lambda: self._switch_profile("Workstation"))
        self.btn_desktop.clicked.connect(lambda: self._switch_device("Desktop"))
        self.btn_laptop.clicked.connect(lambda: self._switch_device("Laptop"))
        self.btn_rescan.clicked.connect(self._rescan)
        self.btn_export.clicked.connect(self._export)

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
        self._do_scan()

    def _do_scan(self):
        if self.is_scanning:
            return
        self.is_scanning = True
        self.btn_rescan.setText("Scanning...")
        self.btn_rescan.setProperty("state", "scanning")
        self.btn_rescan.style().unpolish(self.btn_rescan)
        self.btn_rescan.style().polish(self.btn_rescan)
        QApplication.processEvents()
        QTimer.singleShot(50, self._collect_metrics)

    def _collect_metrics(self):
        try:
            self.metrics = self.collector.collect()
        except Exception as e:
            self.metrics = {"_error": str(e)}

        self.results = {}
        for dev in ("Desktop", "Laptop"):
            self.results[dev] = {}
            for prof in ("Everyday", "Gaming", "Workstation"):
                self.results[dev][prof] = evaluate(self.metrics.copy(), prof, dev == "Laptop")

        if self.metrics.get("is_laptop") and self.device_type == "Desktop":
            self.device_type = "Laptop"

        self.is_scanning = False
        self.btn_rescan.setText("Rescan")
        self.btn_rescan.setProperty("state", "")
        self.btn_rescan.style().unpolish(self.btn_rescan)
        self.btn_rescan.style().polish(self.btn_rescan)

        self._update_subtitle()
        self._render()

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
            f"{machine}  ·  {os_str}  ·  detected: {self.device_type}{admin_note}"
        )

    # ---- Render ----
    def _switch_profile(self, key: str):
        self.current_profile = key
        self._update_tab_styles()
        self._render()

    def _switch_device(self, dev: str):
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
            (self.btn_desktop, "Desktop"),
            (self.btn_laptop, "Laptop"),
        ]:
            active = key == self.device_type
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

        for layout in self.card_columns:
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()

        cats = data.get("categories", [])
        column_heights = [0 for _ in self.card_columns]
        for cat in cats:
            card = CategoryCard(cat)
            card.ensurePolished()
            card.layout().activate()

            col_idx = min(range(len(self.card_columns)), key=column_heights.__getitem__)
            self.card_columns[col_idx].addWidget(card)
            column_heights[col_idx] += card.sizeHint().height() + self.card_columns[col_idx].spacing()

    # ---- Export ----
    def _export(self):
        if not self.results:
            return

        from utils.exporter import export_report
        path = export_report(
            self.metrics,
            self.results,
            self.device_type,
            self.current_profile,
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def _is_windows_admin() -> bool:
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False
