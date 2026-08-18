from __future__ import annotations

import statistics
import sys
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


STYLE = """
QWidget { background: #EEF3F1; color: #151815; font-family: "Microsoft YaHei UI"; }
QFrame#dark { background: #242624; border-radius: 14px; }
QFrame#soft { background: #343733; border-radius: 9px; }
QFrame#blue { background: #AFC7D4; border-radius: 12px; }
QLabel#light { color: #F5F7F3; font-weight: 700; }
"""


def build_window() -> QWidget:
    window = QWidget()
    window.setStyleSheet(STYLE)
    root = QVBoxLayout(window)
    root.setContentsMargins(16, 14, 16, 14)
    root.setSpacing(10)

    header = QLabel("✦  SEEDVR2    图片放大")
    header.setMinimumHeight(40)
    root.addWidget(header)

    body = QHBoxLayout()
    body.setSpacing(12)
    sidebar = QFrame(objectName="dark")
    sidebar.setFixedWidth(300)
    sidebar_layout = QVBoxLayout(sidebar)
    title = QLabel("新建任务", objectName="light")
    sidebar_layout.addWidget(title)
    for text in ("输入图片", "输出目录", "倍率与分块", "开始 4× 放大"):
        card = QFrame(objectName="soft")
        card.setMinimumHeight(86)
        card_layout = QVBoxLayout(card)
        card_layout.addWidget(QLabel(text, objectName="light"))
        sidebar_layout.addWidget(card)
    sidebar_layout.addStretch()
    body.addWidget(sidebar)

    preview = QFrame(objectName="dark")
    preview_layout = QVBoxLayout(preview)
    toolbar = QFrame(objectName="soft")
    toolbar.setMinimumHeight(44)
    preview_layout.addWidget(toolbar)
    canvas = QFrame(objectName="soft")
    preview_layout.addWidget(canvas, 1)
    body.addWidget(preview, 1)
    root.addLayout(body, 1)

    footer = QFrame(objectName="dark")
    footer.setMinimumHeight(68)
    footer_layout = QHBoxLayout(footer)
    footer_layout.addWidget(QLabel("●  Worker 已就绪", objectName="light"))
    footer_layout.addStretch()
    footer_layout.addWidget(QLabel("0%", objectName="light"))
    root.addWidget(footer)
    window.resize(1120, 780)
    return window


def main() -> int:
    app = QApplication(sys.argv)
    window = build_window()
    window.show()
    app.processEvents()
    samples: list[float] = []
    for index in range(100):
        width = 1040 + (index % 20) * 18
        height = 720 + (index % 15) * 10
        started = time.perf_counter()
        window.resize(width, height)
        app.processEvents()
        samples.append((time.perf_counter() - started) * 1000)
    p95 = statistics.quantiles(samples, n=20)[18]
    print(f"samples={len(samples)} median_ms={statistics.median(samples):.3f} p95_ms={p95:.3f} max_ms={max(samples):.3f}")
    window.close()
    return 0 if p95 <= 33 else 1


if __name__ == "__main__":
    raise SystemExit(main())
