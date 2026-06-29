"""Collapsible category section — a dropdown row that shows the score when
collapsed and the full findings/upgrade when expanded."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Reuse the existing finding/upgrade renderers so collapsed and expanded views
# stay visually identical to the rest of the app.
from gui.card_widget import _finding_row, _upgrade_section, _word_of
from scoring.engine import _score_hex as score_hex


class _Header(QWidget):
    """Clickable header strip. Emits a callback on left-click."""

    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self._on_click = on_click
        self.setObjectName("sectionHeader")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mousePressEvent(event)


class CollapsibleSection(QFrame):
    """A single category rendered as an expandable dropdown."""

    def __init__(self, category_result, expanded: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("sectionCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._expanded = expanded
        self._build(category_result)

    def _build(self, cat):
        scored = getattr(cat, "scored", True)
        color = score_hex(cat.score) if scored else "#8B94A7"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Header (always visible) ----
        header = _Header(self.toggle)
        h = QHBoxLayout(header)
        h.setContentsMargins(14, 11, 16, 11)
        h.setSpacing(12)

        self._chevron = QLabel("▸")  # ▸
        self._chevron.setFixedWidth(12)
        self._chevron.setStyleSheet("color: #8B94A7; font-size: 12px;")
        h.addWidget(self._chevron, 0, Qt.AlignmentFlag.AlignVCenter)

        badge = QLabel("N/A" if not scored else str(cat.score))
        badge.setObjectName("scoreBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(48, 32)
        badge.setStyleSheet(
            f"QLabel#scoreBadge {{ color: {color}; border: 1px solid {color};"
            f" border-radius: 8px; font-size: 15px; font-weight: bold;"
            f" background: transparent; }}"
        )
        h.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(1)
        name = QLabel(f"{cat.icon}  {cat.name}")
        name.setStyleSheet("font-size: 14px; font-weight: bold; color: #EDF0F6;")
        title_box.addWidget(name)
        stat = QLabel(cat.stat)
        stat.setStyleSheet("color: #8B94A7; font-size: 11.5px;")
        title_box.addWidget(stat)
        h.addLayout(title_box, 1)

        word = getattr(cat, "status", "") or (_word_of(cat.score) if scored else "Unavailable")
        status = QLabel(word)
        status.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")
        h.addWidget(status, 0, Qt.AlignmentFlag.AlignVCenter)

        root.addWidget(header)

        # ---- Body (toggled) ----
        self._body = QWidget()
        self._body.setObjectName("sectionBody")
        self._body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        b = QVBoxLayout(self._body)
        b.setContentsMargins(18, 6, 16, 16)
        b.setSpacing(0)
        self._populate(b, cat)
        root.addWidget(self._body)

        self._body.setVisible(self._expanded)
        self._sync_chevron()

    def _populate(self, b, cat):
        scored = getattr(cat, "scored", True)

        conf = QLabel(f"Confidence: {getattr(cat, 'confidence', 'Medium')}")
        conf.setStyleSheet("color: #9AA3B5; font-size: 11px;")
        b.addWidget(conf)

        real = [f for f in cat.findings if f.severity != "Info"]
        info = [f for f in cat.findings if f.severity == "Info" and f.title]

        if not scored:
            lbl = QLabel(getattr(cat, "unavailable_reason", "This check was unavailable."))
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #B8C0D0; font-size: 12px; margin-top: 10px;")
            b.addWidget(lbl)
        elif not real:
            ok = QLabel("✓  No issues found — looking great.")
            ok.setStyleSheet("color: #2DD4A7; font-size: 12.5px; margin-top: 10px;")
            b.addWidget(ok)
        else:
            # Expanded view has room, so show every finding (not just the top 3).
            for finding in real:
                b.addLayout(_finding_row(finding))

        if info:
            for finding in info:
                row = _finding_row(finding)
                b.addLayout(row)

        if cat.upgrade:
            b.addLayout(_upgrade_section(cat.upgrade))

    # ---- expand / collapse ----
    def toggle(self):
        self.set_expanded(not self._expanded)

    def set_expanded(self, value: bool):
        if value == self._expanded:
            return
        self._expanded = value
        self._body.setVisible(value)
        self._sync_chevron()
        self.updateGeometry()

    def _sync_chevron(self):
        self._chevron.setText("▾" if self._expanded else "▸")  # ▾ / ▸
