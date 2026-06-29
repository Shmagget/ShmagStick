"""Animated circular gauge widget using QPainter."""

from __future__ import annotations

from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPaintEvent
from PyQt6.QtWidgets import QWidget


class GaugeWidget(QWidget):
    """Animated circular score gauge.

    Paints a donut-style gauge with:
    - Dark background ring
    - Colored score arc (dash pattern)
    - Rotated -90 degrees so fill starts at the top
    - Center text with score and /100 label
    """

    def __init__(self, size: int = 84, thickness: int = 9, parent=None):
        super().__init__(parent)
        self._score = 0
        self._display_score = 0  # animated current value
        self._size = size
        self._thickness = thickness
        self._animating = False
        self._unavailable = False
        self.setFixedSize(size, size)

    def setScore(self, score: int, animate: bool = True):
        """Set the target score. Animates from current value if animate=True."""
        self._score = max(0, min(100, score))
        self._unavailable = False
        if not animate:
            self._display_score = self._score
            self.update()
            return

        if self._animating:
            # Already animating — just update target
            self._anim_target = self._score
            self.update()
            return

        self._animating = True
        self._anim_target = self._score
        self._anim_start = self._display_score
        self._anim_frame = 0
        self._anim_total_frames = 20  # ~1100ms at 18fps
        self._anim_timer_id = self.startTimer(55)

    def setUnavailable(self) -> None:
        self._unavailable = True
        self._animating = False
        self._display_score = 0
        self.update()

    def timerEvent(self, event):
        if not self._animating:
            self.killTimer(event.timerId())
            return

        self._anim_frame += 1
        t = min(1.0, self._anim_frame / self._anim_total_frames)
        # Ease-out cubic
        eased = 1 - (1 - t) ** 3
        self._display_score = round(
            self._anim_start + (self._anim_target - self._anim_start) * eased
        )
        self.update()

        if t >= 1.0:
            self._animating = False
            self.killTimer(event.timerId())

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = self._size
        thick = self._thickness
        radius = (size - thick) / 2 - 3
        cx = size / 2
        cy = size / 2
        circumference = 2 * 3.14159265 * radius

        # Background ("track") arc
        bg_pen = QPen(QColor("#222734"), thick)
        bg_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(bg_pen)
        painter.drawArc(QRectF(cx - radius, cy - radius, radius * 2, radius * 2),
                        0, 360 * 16)

        # Score arc
        score_fraction = 0 if self._unavailable else self._display_score / 100.0
        dash_len = circumference * score_fraction
        gap_len = circumference - dash_len

        if dash_len > 0.5:
            score_color = QColor(_score_to_color(self._display_score))
            arc_pen = QPen(score_color, thick)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

            # Use drawArc with start/span angles
            start_angle = -90 * 16  # starts at top
            span_angle = round(score_fraction * 360 * 16)
            painter.setPen(arc_pen)
            painter.drawArc(QRectF(cx - radius, cy - radius, radius * 2, radius * 2),
                            start_angle, span_angle)

        # Score text
        painter.setPen(QColor("#FFFFFF"))
        font_size = round(size * 0.31)
        painter.setFont(self._font_for_size(font_size))
        score_text = "N/A" if self._unavailable else str(self._display_score)
        text_rect = QRectF(0, size * 0.22, size, size * 0.35)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, score_text)

        # "/100" text
        painter.setPen(QColor("#8B94A7"))
        small_size = round(size * 0.115)
        painter.setFont(self._font_for_size(small_size))
        sub_rect = QRectF(0, size * 0.575, size, size * 0.2)
        painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, "" if self._unavailable else "/100")

    def _font_for_size(self, size: int):
        from PyQt6.QtGui import QFont
        f = QFont("Segoe UI", size, QFont.Weight.Bold)
        return f


def _score_to_color(score: int) -> str:
    if score >= 80:
        return "#2DD4A7"
    if score >= 50:
        return "#F5C451"
    if score >= 30:
        return "#FF935C"
    return "#FF5C77"


def create_gauge(score: int, size: int = 84, thickness: int = 9) -> GaugeWidget:
    """Factory: create a gauge widget with the given initial score."""
    g = GaugeWidget(size=size, thickness=thickness)
    g.setScore(score, animate=False)
    return g
