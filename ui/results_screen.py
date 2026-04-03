"""
ResultsScreen — экран итогов сессии.

Показывает:
  - Крупный счёт (правильных / всего) с цветом по точности
  - Процент точности и короткий текстовый вердикт
  - Прокручиваемый список карточек с ошибками (если есть)
  - Кнопку «Ещё раз» для возврата к выбору колоды
"""

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.models import Card
from core.session_engine import SessionStats


# ══════════════════════════════════════════════════════════════════════════════
# Карточка ошибки (одна строка в списке)
# ══════════════════════════════════════════════════════════════════════════════

class ErrorCardWidget(QFrame):
    """Компактное отображение карточки из списка ошибок."""

    def __init__(self, card: Card, parent=None):
        super().__init__(parent)
        self.setObjectName("resultCard")

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(16)

        # Тип (слово / конструкция)
        kind_label = QLabel("С" if card.kind == "word" else "Ф")
        kind_label.setObjectName("labelHint")
        kind_label.setFixedWidth(16)
        kind_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(kind_label)

        # Сербский текст + транскрипция
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        text_label = QLabel(card.text)
        text_label.setObjectName("labelSecondary")
        text_label.setStyleSheet("font-size: 15px; color: #e8e6f0;")
        text_label.setWordWrap(True)
        text_col.addWidget(text_label)

        if card.phonetic_transcription:
            phon_label = QLabel(card.phonetic_transcription)
            phon_label.setObjectName("labelPhonetic")
            phon_label.setStyleSheet("font-size: 12px;")
            text_col.addWidget(phon_label)

        row.addLayout(text_col, stretch=1)

        # Перевод
        trans_label = QLabel(card.translation)
        trans_label.setObjectName("labelSecondary")
        trans_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        trans_label.setWordWrap(True)
        trans_label.setMaximumWidth(220)
        row.addWidget(trans_label)


# ══════════════════════════════════════════════════════════════════════════════
# Главный экран результатов
# ══════════════════════════════════════════════════════════════════════════════

class ResultsScreen(QWidget):

    # Вердикты по точности
    _VERDICTS = [
        (1.00, "Отлично!",         "#4caf82"),
        (0.80, "Хорошо",           "#4caf82"),
        (0.60, "Неплохо",          "#9b99aa"),
        (0.40, "Нужно повторить",  "#e8a84c"),
        (0.00, "Продолжай учить!", "#e05c5c"),
    ]

    def __init__(self, on_restart: Callable, parent=None):
        super().__init__(parent)
        self._on_restart = on_restart
        self._build_ui()

    # ---------- построение UI ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 32, 48, 32)
        root.setSpacing(0)

        # ── Верхний блок: счёт ──────────────────────────────────────────────
        score_block = QVBoxLayout()
        score_block.setSpacing(6)
        score_block.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._score_label = QLabel()
        self._score_label.setObjectName("labelScore")
        self._score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_block.addWidget(self._score_label)

        self._verdict_label = QLabel()
        self._verdict_label.setObjectName("labelTitle")
        self._verdict_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._verdict_label.setStyleSheet("font-size: 18px;")
        score_block.addWidget(self._verdict_label)

        self._accuracy_label = QLabel()
        self._accuracy_label.setObjectName("labelSecondary")
        self._accuracy_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_block.addWidget(self._accuracy_label)

        root.addLayout(score_block)
        root.addSpacing(28)

        # ── Разделитель + заголовок ошибок ──────────────────────────────────
        self._errors_header = QLabel()
        self._errors_header.setObjectName("labelSecondary")
        self._errors_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self._errors_header)

        root.addSpacing(8)

        # ── Прокручиваемый список ошибок ────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._errors_container = QWidget()
        self._errors_layout = QVBoxLayout(self._errors_container)
        self._errors_layout.setContentsMargins(0, 0, 0, 0)
        self._errors_layout.setSpacing(6)
        self._errors_layout.addStretch()

        self._scroll.setWidget(self._errors_container)
        root.addWidget(self._scroll, stretch=1)

        root.addSpacing(24)

        # ── Кнопка «Ещё раз» ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._btn_restart = QPushButton("← Выбрать режим")
        self._btn_restart.setObjectName("btnAccent")
        self._btn_restart.setFixedHeight(48)
        self._btn_restart.setMinimumWidth(200)
        self._btn_restart.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_restart.clicked.connect(self._on_restart)
        btn_row.addWidget(self._btn_restart)

        btn_row.addStretch()
        root.addLayout(btn_row)

    # ---------- публичный API ----------

    def show_stats(self, stats: SessionStats) -> None:
        """Заполнить экран данными после завершения сессии."""
        self._update_score(stats)
        self._update_errors(stats.error_cards)

    # ---------- внутренняя логика ----------

    def _update_score(self, stats: SessionStats) -> None:
        acc = stats.accuracy

        # Цвет счёта
        score_color = "#4caf82" if acc >= 0.6 else "#e05c5c"
        self._score_label.setText(f"{stats.correct} / {stats.total}")
        self._score_label.setStyleSheet(
            f"font-size: 56px; font-weight: 700; color: {score_color};"
        )

        # Вердикт
        verdict, v_color = self._get_verdict(acc)
        self._verdict_label.setText(verdict)
        self._verdict_label.setStyleSheet(f"font-size: 20px; color: {v_color};")

        # Точность
        errors_txt = (
            f"  ·  {self._errors_noun_err(stats.errors)}" if stats.errors else "  ·  без ошибок"
        )
        self._accuracy_label.setText(f"{acc:.0%} правильных{errors_txt}")

    def _update_errors(self, error_cards: list[Card]) -> None:
        # Очистить старый список
        while self._errors_layout.count() > 1:  # оставить stretch
            item = self._errors_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not error_cards:
            self._errors_header.setText("Ошибок нет — отличная работа!")
            self._scroll.setVisible(False)
            return

        noun = self._errors_noun(len(error_cards))
        self._errors_header.setText(f"Карточки с ошибками ({noun}):")
        self._scroll.setVisible(True)

        for card in error_cards:
            widget = ErrorCardWidget(card)
            self._errors_layout.insertWidget(
                self._errors_layout.count() - 1,  # перед stretch
                widget,
            )

    def _get_verdict(self, accuracy: float) -> tuple[str, str]:
        for threshold, text, color in self._VERDICTS:
            if accuracy >= threshold:
                return text, color
        return "Продолжай!", "#e05c5c"

    @staticmethod
    def _errors_noun_err(n: int) -> str:
        """1 ошибка, 2 ошибки, 5 ошибок."""
        if 11 <= n % 100 <= 14:
            return f"{n} ошибок"
        r = n % 10
        if r == 1:
            return f"{n} ошибка"
        if 2 <= r <= 4:
            return f"{n} ошибки"
        return f"{n} ошибок"

    @staticmethod
    def _errors_noun(n: int) -> str:
        """Правильное склонение: 1 карточка, 2 карточки, 5 карточек."""
        if 11 <= n % 100 <= 14:
            return f"{n} карточек"
        r = n % 10
        if r == 1:
            return f"{n} карточка"
        if 2 <= r <= 4:
            return f"{n} карточки"
        return f"{n} карточек"
