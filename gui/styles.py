"""QSS dark-theme stylesheet for the ShmagStick GUI.

"Slate" — a modern SaaS-analytics palette: cool neutral-slate base, a single
confident indigo accent, hairline borders, and subtle vertical gradients.
Only PyQt6-supported QSS properties are used (no box-shadow / line-height /
letter-spacing / transitions — depth is done in code via QGraphicsDropShadowEffect).
"""

# --- Palette ---------------------------------------------------------------
BG          = "#0B0D12"
SURFACE     = "#14171F"
SURFACE_ALT = "#181C26"
BORDER      = "#262B38"
BORDER_SOFT = "#1F2430"
TEXT        = "#EDF0F6"
TEXT_MUTED  = "#8B94A7"
ACCENT      = "#6E8BFF"
GOOD        = "#2DD4A7"
WARN        = "#F5C451"
ORANGE      = "#FF935C"
BAD         = "#FF5C77"
UPGRADE     = "#F2C26B"

STYLESHEET = """
QMainWindow, QWidget#root {
    background: #0B0D12;
}

QWidget {
    color: #EDF0F6;
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}

/* --- Profile tabs --- */
QPushButton[role="tab"] {
    background: #14171F;
    color: #8B94A7;
    font-weight: 600;
    font-size: 13px;
    border: 1px solid #262B38;
    border-radius: 9px;
    padding: 8px 17px;
    margin-right: 4px;
    min-height: 34px;
}
QPushButton[role="tab"]:hover {
    background: #1A1F2B;
    color: #C2C9D6;
    border-color: #313849;
}
QPushButton[role="tab"][active="true"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2A3350, stop:1 #1F2740);
    color: #FFFFFF;
    border-color: #6E8BFF;
}

/* --- Action buttons (Rescan / Export) --- */
QPushButton[role="action"] {
    background: #181C26;
    color: #C7D2EA;
    font-weight: 600;
    font-size: 13px;
    border: 1px solid #2C3346;
    border-radius: 9px;
    padding: 8px 17px;
    min-height: 34px;
}
QPushButton[role="action"]:hover {
    background: #1F2533;
    border-color: #3A4358;
    color: #EDF0F6;
}
QPushButton[role="action"][state="scanning"] {
    background: #11352A;
    color: #2DD4A7;
    border-color: #1E4D3E;
}

/* --- Hero section --- */
#heroSection {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #171B26, stop:1 #12151D);
    border: 1px solid #262B38;
    border-radius: 18px;
}

/* --- Device-type panel (right side of hero) --- */
#devicePanel {
    background: #12151C;
    border: 1px solid #262B38;
    border-radius: 14px;
}

#summaryPanel {
    background: #12151C;
    border: 1px solid #262B38;
    border-radius: 12px;
}

QProgressBar {
    background: #222734;
    border: none;
    border-radius: 2px;
}
QProgressBar::chunk {
    background: #6E8BFF;
    border-radius: 2px;
}

/* --- Category cards (also set inline for the gradient) --- */
CategoryCard {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #161A23, stop:1 #13161E);
    border: 1px solid #262B38;
    border-radius: 16px;
}

/* --- Collapsible category sections (dropdowns) --- */
#sectionCard {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #161A23, stop:1 #13161E);
    border: 1px solid #262B38;
    border-radius: 12px;
}
#sectionHeader {
    background: transparent;
    border-radius: 12px;
}
#sectionHeader:hover {
    background: #1A1F2B;
}
#sectionBody {
    background: #101319;
    border-top: 1px solid #1F2430;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
}
QLabel#scoreBadge { font-size: 15px; font-weight: bold; }
QLabel#deepHeader { color: #B9C6E8; font-size: 12px; font-weight: bold; }

/* --- Scroll area: themed so no light band bleeds on the right --- */
QScrollArea {
    border: none;
    background: transparent;
}
#scrollContent {
    background: transparent;
}
QAbstractScrollArea::corner {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px 2px 2px 0;
}
QScrollBar::handle:vertical {
    background: #2C3242;
    border-radius: 5px;
    min-height: 36px;
}
QScrollBar::handle:vertical:hover {
    background: #3A4256;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    border: none;
    background: transparent;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

/* --- Tooltips --- */
QToolTip {
    background: #181C26;
    color: #EDF0F6;
    border: 1px solid #2C3346;
    border-radius: 6px;
    padding: 4px 8px;
}

/* --- Labels (object-name targeted) --- */
QLabel#subtitle      { color: #8B94A7; font-size: 12px; }
QLabel#categoryName  { color: #EDF0F6; font-size: 14px; font-weight: bold; }
QLabel#categoryStat  { color: #8B94A7; font-size: 11.5px; }
QLabel#categoryWord  { font-size: 11px; font-weight: bold; }
QLabel#gradeLabel    { color: #8B94A7; font-size: 14px; }
QLabel#blurb         { color: #9AA3B5; font-size: 13px; }
QLabel#footer        { color: #8B94A7; font-size: 11px; }
"""
