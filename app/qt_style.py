from __future__ import annotations


COLORS = {
    "background": "#EEF3F1",
    "surface": "#F8FAF9",
    "surface_soft": "#DCE7EC",
    "surface_dark": "#242624",
    "surface_dark_soft": "#343733",
    "surface_blue": "#AFC7D4",
    "accent": "#DFFF00",
    "text": "#151815",
    "text_on_dark": "#F5F7F3",
    "text_muted": "#667069",
    "text_muted_dark": "#ADB5AD",
    "border": "#D5DEDA",
    "warning": "#A96600",
}


APP_STYLE = """
* { font-family: "Microsoft YaHei UI"; font-size: 13px; }
QMainWindow, QWidget#page { background: #EEF3F1; color: #151815; }
QFrame#darkPanel { background: #242624; border-radius: 14px; }
QFrame#softPanel { background: #343733; border-radius: 9px; }
QFrame#inputCard { background: #2E312E; border-radius: 9px; }
QFrame#inputSummary { background: #393D39; border-radius: 7px; }
QFrame#warningCard { background: #36362C; border-radius: 9px; }
QFrame#toolbar { background: #343733; border-radius: 8px; }
QFrame#footer { background: #242624; border-radius: 12px; }
QFrame#divider { background: #4A4E4A; min-width: 1px; max-width: 1px; }
QLabel#heading { font-size: 24px; font-weight: 700; }
QLabel#brand { color: #151815; font-weight: 700; }
QLabel#sectionTitle { color: #F5F7F3; font-size: 18px; font-weight: 700; }
QLabel#lightStrong { color: #F5F7F3; font-weight: 700; }
QLabel#light { color: #F5F7F3; }
QLabel#muted { color: #667069; }
QLabel#mutedDark { color: #ADB5AD; }
QLabel#warning { color: #E5DCB5; font-size: 12px; }
QLabel#badge { background: #DCE7EC; border-radius: 8px; padding: 7px 11px; font-weight: 700; }
QLabel#darkBadge { background: #343733; color: #ADB5AD; border-radius: 7px; padding: 5px 9px; }
QPushButton { border: 0; border-radius: 8px; padding: 9px 13px; font-weight: 700; }
QPushButton:focus { outline: none; border: 1px solid #86A6B6; }
QPushButton#primary { background: #DFFF00; color: #151815; }
QPushButton#primary:hover { background: #CEEF00; }
QPushButton#secondary { background: #393D39; color: #F5F7F3; }
QPushButton#secondary:hover { background: #4A4F4A; }
QPushButton#blue { background: #AFC7D4; color: #151815; }
QPushButton#blue:hover { background: #9DB9C8; }
QPushButton#outline { background: transparent; color: #F5F7F3; border: 1px solid #59605B; }
QPushButton#outline:hover { background: #343733; }
QPushButton:disabled { background: #303330; color: #737B75; border-color: #414641; }
QComboBox { background: #343733; color: #F5F7F3; border: 1px solid #4B504B; border-radius: 8px; padding: 8px 30px 8px 10px; font-weight: 700; }
QComboBox:hover, QComboBox:focus { border-color: #86A6B6; }
QComboBox:disabled { color: #737B75; border-color: #414641; }
QComboBox::drop-down { border: 0; width: 28px; }
QComboBox::down-arrow { image: url(assets/chevron-down.svg); width: 12px; height: 8px; }
QComboBox QAbstractItemView { background: #2E312E; color: #F5F7F3; border: 1px solid #59605B; border-radius: 8px; selection-background-color: #AFC7D4; selection-color: #151815; padding: 5px; outline: 0; }
QPlainTextEdit { background: #181A18; color: #DCE4DD; border: 0; border-radius: 7px; padding: 8px; font-family: Consolas; font-size: 12px; }
QToolTip { background: #242624; color: #F5F7F3; border: 1px solid #59605B; padding: 5px; }
"""
