"""
CardScreen — экран карточки.

Два режима в одном виджете через QStackedWidget:
  - AnkiFlipWidget   — показать лицо → перевернуть → оценить себя
  - MultiChoiceWidget — выбрать правильный перевод из 4 вариантов

Режим выбирается случайно (50/50) для каждой карточки.
"""

import random
from typing import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.models import Card
from core.session_engine import SessionEngine


# ══════════════════════════════════════════════════════════════════════════════
# Вспомогательные виджеты: лицо и оборот карточки
# ══════════════════════════════════════════════════════════════════════════════

class CardFaceWidget(QWidget):
    """Лицо карточки: сербский текст + МФА + произношение."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._kind_label = QLabel()
        self._kind_label.setObjectName("labelHint")
        self._kind_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._kind_label)

        layout.addSpacing(6)

        self._text_label = QLabel()
        self._text_label.setObjectName("labelCardText")
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setWordWrap(True)
        layout.addWidget(self._text_label)

        layout.addSpacing(4)

        self._phonetic_label = QLabel()
        self._phonetic_label.setObjectName("labelPhonetic")
        self._phonetic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._phonetic_label.setWordWrap(True)
        layout.addWidget(self._phonetic_label)

        self._pronunc_label = QLabel()
        self._pronunc_label.setObjectName("labelPronunciation")
        self._pronunc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pronunc_label.setWordWrap(True)
        layout.addWidget(self._pronunc_label)

    def load(self, card: Card):
        self._kind_label.setText("слово" if card.kind == "word" else "конструкция")
        self._text_label.setText(card.text)
        self._phonetic_label.setText(card.phonetic_transcription)
        self._pronunc_label.setText(card.pronunciation_description)


class CardBackWidget(QWidget):
    """Оборот карточки: перевод + заметка."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 16, 32, 24)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        layout.addSpacing(8)

        self._translation_label = QLabel()
        self._translation_label.setObjectName("labelTranslation")
        self._translation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._translation_label.setWordWrap(True)
        layout.addWidget(self._translation_label)

        self._note_label = QLabel()
        self._note_label.setObjectName("labelNote")
        self._note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._note_label.setWordWrap(True)
        layout.addWidget(self._note_label)

    def load(self, card: Card):
        self._translation_label.setText(card.translation)
        note = card.note.strip()
        self._note_label.setText(note)
        self._note_label.setVisible(bool(note))


# ══════════════════════════════════════════════════════════════════════════════
# Режим 1: Anki-flip
# ══════════════════════════════════════════════════════════════════════════════

class AnkiFlipWidget(QWidget):
    """Лицо → «Показать» → оборот → «Знаю» / «Не знаю»."""

    def __init__(self, on_answer: Callable[[bool], None], parent=None):
        super().__init__(parent)
        self._on_answer = on_answer

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # Фрейм карточки
        self._card_frame = QFrame()
        self._card_frame.setObjectName("cardFrame")
        self._card_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        cf = QVBoxLayout(self._card_frame)
        cf.setContentsMargins(0, 0, 0, 0)
        cf.setSpacing(0)

        self._face = CardFaceWidget()
        cf.addWidget(self._face)

        self._back = CardBackWidget()
        self._back.setVisible(False)
        cf.addWidget(self._back)

        root.addWidget(self._card_frame)

        # Кнопка «Показать»
        self._btn_show = QPushButton("Показать перевод")
        self._btn_show.setObjectName("btnAccent")
        self._btn_show.setFixedHeight(48)
        self._btn_show.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_show.clicked.connect(self._flip)
        root.addWidget(self._btn_show)

        # Кнопки оценки
        answer_row = QHBoxLayout()
        answer_row.setSpacing(12)

        self._btn_wrong = QPushButton("✗  Не знаю")
        self._btn_wrong.setObjectName("btnWrong")
        self._btn_wrong.setFixedHeight(48)
        self._btn_wrong.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_wrong.clicked.connect(lambda: self._submit(False))

        self._btn_correct = QPushButton("✓  Знаю")
        self._btn_correct.setObjectName("btnCorrect")
        self._btn_correct.setFixedHeight(48)
        self._btn_correct.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_correct.clicked.connect(lambda: self._submit(True))

        answer_row.addWidget(self._btn_wrong)
        answer_row.addWidget(self._btn_correct)

        self._answer_widget = QWidget()
        self._answer_widget.setLayout(answer_row)
        self._answer_widget.setVisible(False)
        root.addWidget(self._answer_widget)

    def load(self, card: Card):
        self._face.load(card)
        self._back.load(card)
        self._set_flipped(False)
        self._card_frame.setObjectName("cardFrame")
        self._card_frame.setStyle(self._card_frame.style())
        self._btn_wrong.setEnabled(True)
        self._btn_correct.setEnabled(True)

    def _flip(self):
        self._set_flipped(True)
        self._card_frame.setObjectName("cardFrameFlipped")
        self._card_frame.setStyle(self._card_frame.style())

    def _set_flipped(self, flipped: bool):
        self._back.setVisible(flipped)
        self._btn_show.setVisible(not flipped)
        self._answer_widget.setVisible(flipped)

    def _submit(self, correct: bool):
        self._btn_correct.setEnabled(False)
        self._btn_wrong.setEnabled(False)
        QTimer.singleShot(150, lambda: self._on_answer(correct))


# ══════════════════════════════════════════════════════════════════════════════
# Режим 2: Multiple choice
# ══════════════════════════════════════════════════════════════════════════════

class MultiChoiceWidget(QWidget):
    """Показать сербский текст → выбрать правильный перевод из 4 вариантов."""

    def __init__(self, on_answer: Callable[[bool], None], parent=None):
        super().__init__(parent)
        self._on_answer = on_answer
        self._correct_id: str = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # Фрейм карточки — только лицо
        card_frame = QFrame()
        card_frame.setObjectName("cardFrame")
        card_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        cf = QVBoxLayout(card_frame)
        cf.setContentsMargins(0, 0, 0, 0)

        self._face = CardFaceWidget()
        cf.addWidget(self._face)

        root.addWidget(card_frame)
        root.addSpacing(4)

        # 4 кнопки вариантов
        self._choice_buttons: list[QPushButton] = []
        for _ in range(4):
            btn = QPushButton()
            btn.setObjectName("btnChoice")
            btn.setMinimumHeight(52)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked, b=btn: self._on_choice(b))
            root.addWidget(btn)
            self._choice_buttons.append(btn)

    def load(self, card: Card, distractors: list[Card]):
        self._face.load(card)
        self._correct_id = card.element_id

        options = [card] + distractors[:3]
        random.shuffle(options)

        for i, btn in enumerate(self._choice_buttons):
            if i < len(options):
                opt = options[i]
                btn.setText(opt.translation)
                btn.setProperty("element_id", opt.element_id)
                btn.setObjectName("btnChoice")
                btn.setStyle(btn.style())
                btn.setEnabled(True)
                btn.setVisible(True)
            else:
                btn.setVisible(False)

    def _on_choice(self, clicked_btn: QPushButton):
        chosen_id = clicked_btn.property("element_id")
        correct = (chosen_id == self._correct_id)

        for btn in self._choice_buttons:
            btn.setEnabled(False)
            bid = btn.property("element_id")
            if bid == self._correct_id:
                btn.setObjectName("btnChoiceCorrect")
            elif btn is clicked_btn and not correct:
                btn.setObjectName("btnChoiceWrong")
            btn.setStyle(btn.style())

        QTimer.singleShot(900, lambda: self._on_answer(correct))


# ══════════════════════════════════════════════════════════════════════════════
# Главный экран карточек
# ══════════════════════════════════════════════════════════════════════════════

class CardScreen(QWidget):

    def __init__(self, engine: SessionEngine, on_finish: Callable, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._on_finish = on_finish

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 20, 40, 28)
        root.setSpacing(12)

        # ── Шапка: прогресс + счётчик ──
        header = QHBoxLayout()
        header.setSpacing(12)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        header.addWidget(self._progress_bar, stretch=1)

        self._counter_label = QLabel()
        self._counter_label.setObjectName("labelSecondary")
        self._counter_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._counter_label.setFixedWidth(56)
        header.addWidget(self._counter_label)

        root.addLayout(header)

        # ── Переключатель режимов ──
        self._mode_stack = QStackedWidget()

        self._anki = AnkiFlipWidget(on_answer=self._on_answered)
        self._multi = MultiChoiceWidget(on_answer=self._on_answered)

        self._mode_stack.addWidget(self._anki)   # 0
        self._mode_stack.addWidget(self._multi)  # 1

        root.addWidget(self._mode_stack, stretch=1)

    # ---------- публичный API ----------

    def begin(self):
        """Вызвать перед показом экрана — загружает первую карточку."""
        self._show_current()

    # ---------- внутренняя логика ----------

    def _show_current(self):
        card = self._engine.current_card()
        if card is None:
            self._on_finish()
            return

        pos, total = self._engine.progress_tuple()
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(pos - 1)
        self._counter_label.setText(f"{pos} / {total}")

        # 50/50 между режимами; fallback на anki если мало дистракторов
        use_multi = random.random() < 0.5
        if use_multi:
            distractors = self._engine.get_distractors(card, count=3)
            if len(distractors) >= 1:
                self._mode_stack.setCurrentIndex(1)
                self._multi.load(card, distractors)
                return

        self._mode_stack.setCurrentIndex(0)
        self._anki.load(card)

    def _on_answered(self, correct: bool):
        self._engine.submit_answer(correct)
        if not self._engine.is_finished():
            pos, total = self._engine.progress_tuple()
            self._progress_bar.setValue(pos - 1)
        QTimer.singleShot(80, self._advance)

    def _advance(self):
        if self._engine.is_finished():
            self._on_finish()
        else:
            self._show_current()
