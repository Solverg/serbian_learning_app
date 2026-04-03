"""
DeckSelectorScreen — стартовый экран.

Позволяет выбрать режим (слова / конструкции / смешанный)
и задать размер сессии, затем вызывает on_start.
"""

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.session_engine import DeckMode


class DeckSelectorScreen(QWidget):

    _MODES: list[tuple[DeckMode, str, str]] = [
        ("words",         "Слова",        "Только словарные слова"),
        ("constructions", "Конструкции",  "Готовые фразы и выражения"),
        ("mixed",         "Смешанный",    "Слова и конструкции вместе"),
    ]

    def __init__(self, on_start: Callable[[DeckMode, int], None], parent=None):
        super().__init__(parent)
        self._on_start = on_start
        self._selected_mode: DeckMode = "mixed"
        self._mode_buttons: dict[DeckMode, QPushButton] = {}

        self._build_ui()
        self._select_mode("mixed")

    # ---------- построение UI ----------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(60, 50, 60, 50)
        root.setSpacing(0)

        # Заголовок
        title = QLabel("Сербский язык")
        title.setObjectName("labelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel("Карточки для изучения")
        subtitle.setObjectName("labelSecondary")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        root.addSpacing(40)

        # Кнопки выбора режима
        mode_label = QLabel("Режим")
        mode_label.setObjectName("labelSecondary")
        root.addWidget(mode_label)
        root.addSpacing(10)

        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        for mode, name, desc in self._MODES:
            btn = QPushButton(f"{name}\n{desc}")
            btn.setObjectName("btnDeck")
            btn.setCheckable(True)
            btn.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            # Две строки текста + крупный внутренний padding из QSS.
            # 72px недостаточно на некоторых DPI/шрифтах и текст визуально "выпирает".
            btn.setFixedHeight(110)
            btn.clicked.connect(lambda checked, m=mode: self._select_mode(m))
            self._btn_group.addButton(btn)
            self._mode_buttons[mode] = btn
            root.addWidget(btn)
            root.addSpacing(8)

        root.addSpacing(32)

        # Размер сессии
        size_row = QHBoxLayout()
        size_label = QLabel("Карточек за сессию")
        size_label.setObjectName("labelSecondary")
        size_row.addWidget(size_label)
        size_row.addStretch()

        self._spin = QSpinBox()
        self._spin.setRange(5, 100)
        self._spin.setValue(20)
        self._spin.setSingleStep(5)
        self._spin.setFixedWidth(90)
        size_row.addWidget(self._spin)
        root.addLayout(size_row)

        root.addSpacing(36)

        # Кнопка «Начать»
        self._btn_start = QPushButton("Начать")
        self._btn_start.setObjectName("btnAccent")
        self._btn_start.setFixedHeight(48)
        self._btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_start.clicked.connect(self._on_start_clicked)
        root.addWidget(self._btn_start)

        root.addStretch()

    # ---------- логика ----------

    def _select_mode(self, mode: DeckMode):
        self._selected_mode = mode
        for m, btn in self._mode_buttons.items():
            btn.setChecked(m == mode)

    def _on_start_clicked(self):
        self._on_start(self._selected_mode, self._spin.value())
