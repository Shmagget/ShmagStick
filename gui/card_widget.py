"""Category card widget — shows a gauge, findings, and upgrade suggestion."""

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

from scoring.engine import _score_hex as score_hex


CARD_WIDTH = 336

SEV_COLORS = {
    "Critical": "#FF5C77",
    "High": "#FF935C",
    "Medium": "#F5C451",
    "Low": "#8B94A7",
    "Info": "#6E8BFF",
}


class CategoryCard(QFrame):
    """A single category card: gauge + findings + upgrade."""

    def __init__(self, category_result, parent=None):
        super().__init__(parent)
        self.setObjectName("categoryCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)
        self._build(category_result)

    def _build(self, cat):
        self.setFixedWidth(CARD_WIDTH)
        self.setStyleSheet("""
            CategoryCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                            stop:0 #161A23, stop:1 #13161E);
                border: 1px solid #262B38;
                border-radius: 16px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 16, 16)
        main_layout.setSpacing(0)

        # -- Header: gauge + info --
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(0)

        from gui.gauge_widget import GaugeWidget
        gauge = GaugeWidget(size=78, thickness=7)
        gauge.setScore(cat.score, animate=False)
        hdr.addWidget(gauge, 0, Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setContentsMargins(16, 2, 0, 0)
        info.setSpacing(3)

        name_lbl = QLabel(f"{cat.icon}  {cat.name}")
        name_lbl.setObjectName("categoryName")
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(
            "QLabel#categoryName { font-size: 14px; font-weight: bold; color: #EDF0F6; }"
        )
        info.addWidget(name_lbl)

        stat_lbl = QLabel(cat.stat)
        stat_lbl.setObjectName("categoryStat")
        stat_lbl.setWordWrap(True)
        stat_lbl.setStyleSheet(
            "QLabel#categoryStat { color: #8B94A7; font-size: 11.5px; margin-top: 2px; }"
        )
        info.addWidget(stat_lbl)

        word = _word_of(cat.score)
        word_lbl = QLabel(word)
        word_lbl.setObjectName("categoryWord")
        word_lbl.setStyleSheet(f"""
            QLabel#categoryWord {{
                color: {score_hex(cat.score)};
                font-size: 11px;
                font-weight: bold;
                margin-top: 5px;
            }}
        """)
        info.addWidget(word_lbl)

        hdr.addLayout(info, 1)
        main_layout.addLayout(hdr)

        # -- Findings --
        real_findings = [f for f in cat.findings if f.severity != "Info"]
        info_findings = [f for f in cat.findings if f.severity == "Info" and f.title]

        if not real_findings:
            ok = QLabel("✓  No issues found — looking great.")
            ok.setStyleSheet(
                "color: #2DD4A7; font-size: 12.5px; margin-top: 13px; margin-bottom: 2px;"
            )
            main_layout.addWidget(ok)
        else:
            for f in real_findings[:3]:
                main_layout.addLayout(_finding_row(f), 0)
            if len(real_findings) > 3:
                more = QLabel(f"+ {len(real_findings) - 3} more (see Export report for the full list)")
                more.setStyleSheet("color: #8B94A7; font-size: 11px; margin-top: 9px; margin-bottom: 2px;")
                main_layout.addWidget(more)

        if info_findings:
            info_text = "  ·  ".join(f.title for f in info_findings)
            info_lbl = QLabel(info_text)
            info_lbl.setWordWrap(True)
            info_lbl.setStyleSheet(
                "color: #6E7488; font-size: 11px; margin-top: 10px; margin-bottom: 0px;"
            )
            main_layout.addWidget(info_lbl)

        # -- Upgrade --
        if cat.upgrade:
            main_layout.addLayout(_upgrade_section(cat.upgrade))

    def sizeHint(self):
        # Width is fixed; let the height follow the content (masonry layout).
        from PyQt6.QtCore import QSize
        return QSize(CARD_WIDTH, super().sizeHint().height())


def _finding_row(f) -> QVBoxLayout:
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 12, 0, 0)
    layout.setSpacing(0)

    # Title row: chip + title
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)

    chip = QLabel(f.severity.upper())
    chip.setProperty("sev", f.severity)
    chip.setStyleSheet(f"""
        QLabel {{
            background: {SEV_COLORS.get(f.severity, '#6E8BFF')};
            color: #0B0D12;
            border-radius: 4px;
            padding: 1px 7px;
            font-size: 10px;
            font-weight: bold;
        }}
    """)
    chip.setFixedHeight(18)
    row.addWidget(chip, 0, Qt.AlignmentFlag.AlignTop)

    title_lbl = QLabel(f.title)
    title_lbl.setWordWrap(True)
    title_lbl.setStyleSheet("QLabel { font-weight: 600; font-size: 12.5px; color: #EDF0F6; }")
    row.addWidget(title_lbl, 1)

    layout.addLayout(row)

    if f.detail:
        detail = QLabel(f.detail)
        detail.setWordWrap(True)
        detail.setStyleSheet("color: #8B94A7; font-size: 11.5px; margin-top: 4px;")
        layout.addWidget(detail)

    if f.action:
        action = QLabel(f.action)
        action.setWordWrap(True)
        action.setStyleSheet("""
            QLabel {
                color: #B9C6E8; font-size: 11.5px;
                border-left: 2px solid #6E8BFF;
                padding-left: 8px; margin-top: 5px;
            }
        """)
        layout.addWidget(action)

    return layout


UPGRADE_COLORS = {
    "buy": "#F2C26B",
    "ok": "#2DD4A7",
    "free": "#6E8BFF",
    "advisory": "#FF935C",
}


def _upgrade_section(up) -> QVBoxLayout:
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 13, 0, 0)
    layout.setSpacing(0)

    sep = QWidget()
    sep.setFixedHeight(1)
    sep.setStyleSheet("background: #262B38;")
    layout.addWidget(sep)

    color = UPGRADE_COLORS.get(up.kind, "#9AA3B5")
    header = QLabel("\U0001F4A1  SUGGESTED UPGRADE")
    header.setStyleSheet(f"""
        QLabel {{
            color: {color}; font-size: 10px; font-weight: bold;
            margin-top: 11px;
        }}
    """)
    layout.addWidget(header)

    text = QLabel(up.text)
    text.setWordWrap(True)
    text.setStyleSheet(f"QLabel {{ color: {color}; font-size: 12.5px; margin-top: 5px; }}")
    layout.addWidget(text)

    if up.url:
        link = QLabel(f"<a href='{up.url}'>View on Amazon &#8594;</a>")
        link.setOpenExternalLinks(True)
        link.setStyleSheet("""
            QLabel { color: #F2C26B; font-size: 12.5px; font-weight: bold; margin-top: 7px; }
            QLabel a { color: #F2C26B; text-decoration: none; }
            QLabel a:hover { text-decoration: underline; }
        """)
        link.setToolTip(up.url)
        layout.addWidget(link)

    if up.note:
        note = QLabel(up.note)
        note.setWordWrap(True)
        note.setStyleSheet("color: #8B94A7; font-size: 11px; margin-top: 6px;")
        layout.addWidget(note)

    return layout


def _word_of(score: int) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Fair"
    if score >= 30:
        return "Poor"
    return "Critical"
