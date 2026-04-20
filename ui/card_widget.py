"""
CardScreen — экран карточки.

Доступные режимы через QStackedWidget:
  - AnkiFlipWidget    — показать лицо → перевернуть → оценить себя
  - MultiChoiceWidget — выбрать правильный перевод из 4 вариантов
  - FillBlankWidget   — вставить пропущенное слово
  - MatchingWidget    — соотнести 6 слов и 6 переводов

Matching показывается рандомизированно в среднем 1 раз на 20 упражнений.
"""

import random
import re
from typing import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
    """Лицо карточки: сербский или русский текст в зависимости от направления."""

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

    def load(self, card: Card, reverse: bool = False):
        self._kind_label.setText("слово" if card.kind == "word" else "конструкция")
        if reverse:
            self._text_label.setText(card.translation)
            self._phonetic_label.clear()
            self._pronunc_label.clear()
        else:
            self._text_label.setText(card.text)
            self._phonetic_label.setText(card.phonetic_transcription)
            self._pronunc_label.setText(card.pronunciation_description)


class CardBackWidget(QWidget):
    """Оборот карточки: ответ + заметка для прямого/обратного направления."""

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

    def load(self, card: Card, reverse: bool = False):
        if reverse:
            self._translation_label.setText(card.text)
            details = [
                card.phonetic_transcription.strip(),
                card.pronunciation_description.strip(),
                card.note.strip(),
            ]
            note = "\n".join([d for d in details if d])
        else:
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

        self._btn_show = QPushButton("Показать перевод")
        self._btn_show.setObjectName("btnAccent")
        self._btn_show.setFixedHeight(48)
        self._btn_show.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_show.clicked.connect(self._flip)
        root.addWidget(self._btn_show)

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

    def load(self, card: Card, reverse: bool = False):
        self._face.load(card, reverse=reverse)
        self._back.load(card, reverse=reverse)
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
    """Выбрать правильный вариант в прямом или обратном направлении."""

    def __init__(self, on_answer: Callable[[bool], None], parent=None):
        super().__init__(parent)
        self._on_answer = on_answer
        self._correct_id: str = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

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

        self._choice_buttons: list[QPushButton] = []
        for _ in range(4):
            btn = QPushButton()
            btn.setObjectName("btnChoice")
            btn.setMinimumHeight(52)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked, b=btn: self._on_choice(b))
            root.addWidget(btn)
            self._choice_buttons.append(btn)

    def load(self, card: Card, distractors: list[Card], reverse: bool = False):
        self._face.load(card, reverse=reverse)
        self._correct_id = card.element_id

        options = [card] + distractors[:3]
        random.shuffle(options)

        for i, btn in enumerate(self._choice_buttons):
            if i < len(options):
                opt = options[i]
                btn.setText(opt.text if reverse else opt.translation)
                btn.setProperty("element_id", opt.element_id)
                btn.setObjectName("btnChoice")
                btn.setStyle(btn.style())
                btn.setEnabled(True)
                btn.setVisible(True)
            else:
                btn.setVisible(False)

    def _on_choice(self, clicked_btn: QPushButton):
        chosen_id = clicked_btn.property("element_id")
        correct = chosen_id == self._correct_id

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
# Режим 3: Fill in the blank
# ══════════════════════════════════════════════════════════════════════════════

class FillBlankWidget(QWidget):
    """Показать перевод и фразу с пропуском, пользователь вводит недостающее слово."""

    _PUNCT_PATTERN = re.compile(r"^([^\w\u0400-\u04FF\-']*)([\w\u0400-\u04FF\-']+)([^\w\u0400-\u04FF\-']*)$")

    def __init__(self, on_answer: Callable[[bool], None], parent=None):
        super().__init__(parent)
        self._on_answer = on_answer
        self._target_word: str = ""
        self._masked_pattern: str = ""
        self._is_answered = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self._translation_label = QLabel()
        self._translation_label.setObjectName("labelTranslation")
        self._translation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._translation_label.setWordWrap(True)
        root.addWidget(self._translation_label)

        self._sentence_label = QLabel()
        self._sentence_label.setObjectName("labelCardText")
        self._sentence_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sentence_label.setWordWrap(True)
        root.addWidget(self._sentence_label)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Введите пропущенное слово")
        self._input.setMinimumHeight(44)
        self._input.returnPressed.connect(self._check_answer)
        root.addWidget(self._input)

        self._check_button = QPushButton("Проверить")
        self._check_button.setObjectName("btnAccent")
        self._check_button.setFixedHeight(48)
        self._check_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_button.clicked.connect(self._check_answer)
        root.addWidget(self._check_button)

    def load(self, card: Card):
        words = card.text.split()
        self._translation_label.setText(card.translation)
        self._target_word = ""
        self._masked_pattern = ""
        self._is_answered = False

        if len(words) < 2:
            self._sentence_label.setText(card.text)
            self._check_button.setEnabled(False)
            self._input.setReadOnly(True)
            return

        hidden_index = random.randrange(len(words))
        original_word = words[hidden_index]
        prefix, core, suffix = self._split_word_parts(original_word)

        self._target_word = core.lower().strip()
        self._masked_pattern = " ".join(
            words[:hidden_index] + [f"{prefix}_____{suffix}"] + words[hidden_index + 1:]
        )
        self._sentence_label.setText(self._masked_pattern)

        self._input.clear()
        self._input.setReadOnly(False)
        self._input.setStyleSheet("")
        self._check_button.setEnabled(True)
        self._input.setFocus()

    def _split_word_parts(self, word: str) -> tuple[str, str, str]:
        match = self._PUNCT_PATTERN.match(word)
        if match:
            return match.group(1), match.group(2), match.group(3)
        return "", word, ""

    def _check_answer(self):
        if self._is_answered or not self._target_word:
            return

        self._is_answered = True
        self._check_button.setEnabled(False)
        self._input.setReadOnly(True)

        user_answer = self._input.text().strip().lower()
        correct = user_answer == self._target_word

        if correct:
            self._input.setStyleSheet("background-color: #1e5f2b; color: #f2fff5;")
            QTimer.singleShot(850, lambda: self._on_answer(True))
            return

        self._input.setStyleSheet("background-color: #6d1f1f; color: #fff2f2;")
        revealed = f'<span style="color:#6ee7a8;font-weight:600;">{self._target_word}</span>'
        self._sentence_label.setText(self._masked_pattern.replace("_____", revealed, 1))
        QTimer.singleShot(1700, lambda: self._on_answer(False))


# ══════════════════════════════════════════════════════════════════════════════
# Режим 4: Matching — соотнеси слово и перевод (6 × 6)
# ══════════════════════════════════════════════════════════════════════════════

class MatchingWidget(QWidget):
    """
    6 слов слева — 6 переводов справа.
    Пользователь нажимает слово, затем перевод (или наоборот).
    Правильные пары подсвечиваются зелёным и блокируются.

    Упражнение засчитывается одним результатом:
      верно  — все 6 пар без единой ошибки,
      неверно — была хотя бы одна неверная попытка.
    """

    def __init__(self, on_answer: Callable[[bool], None], parent=None):
        super().__init__(parent)
        self._on_answer = on_answer
        self._errors: int = 0
        self._matched: int = 0
        self._id_of_left: dict[QPushButton, str] = {}
        self._id_of_right: dict[QPushButton, str] = {}
        self._selected_left: QPushButton | None = None
        self._selected_right: QPushButton | None = None
        self._used_element_ids: list[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        hint = QLabel("Соотнеси слова и переводы")
        hint.setObjectName("labelHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hint)

        columns = QHBoxLayout()
        columns.setSpacing(12)

        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        right_col = QVBoxLayout()
        right_col.setSpacing(6)

        self._left_btns: list[QPushButton] = []
        self._right_btns: list[QPushButton] = []

        for _ in range(6):
            lb = QPushButton()
            lb.setObjectName("btnChoice")
            lb.setMinimumHeight(52)
            lb.setCursor(Qt.CursorShape.PointingHandCursor)
            lb.clicked.connect(lambda _c, b=lb: self._on_left(b))
            left_col.addWidget(lb)
            self._left_btns.append(lb)

            rb = QPushButton()
            rb.setObjectName("btnChoice")
            rb.setMinimumHeight(52)
            rb.setCursor(Qt.CursorShape.PointingHandCursor)
            rb.clicked.connect(lambda _c, b=rb: self._on_right(b))
            right_col.addWidget(rb)
            self._right_btns.append(rb)

        columns.addLayout(left_col)
        columns.addLayout(right_col)
        root.addLayout(columns, stretch=1)

    def load(self, cards: list[Card]) -> None:
        """Загрузить 6 карточек для матчинга."""
        self._selected_left = None
        self._selected_right = None
        self._errors = 0
        self._matched = 0
        self._id_of_left = {}
        self._id_of_right = {}

        sample = cards[:6]
        self._used_element_ids = [c.element_id for c in sample]
        left_order = sample[:]
        random.shuffle(left_order)
        right_order = sample[:]
        random.shuffle(right_order)

        for i in range(6):
            lb = self._left_btns[i]
            lb.setText(left_order[i].text)
            lb.setProperty("element_id", left_order[i].element_id)
            lb.setObjectName("btnChoice")
            lb.setStyle(lb.style())
            lb.setEnabled(True)
            self._id_of_left[lb] = left_order[i].element_id

            rb = self._right_btns[i]
            rb.setText(right_order[i].translation)
            rb.setProperty("element_id", right_order[i].element_id)
            rb.setObjectName("btnChoice")
            rb.setStyle(rb.style())
            rb.setEnabled(True)
            self._id_of_right[rb] = right_order[i].element_id

    def used_element_ids(self) -> list[str]:
        return list(self._used_element_ids)

    def _on_left(self, btn: QPushButton) -> None:
        if self._selected_left is btn:
            self._deselect_left()
            return
        self._deselect_left()
        self._selected_left = btn
        btn.setObjectName("btnChoiceSelected")
        btn.setStyle(btn.style())
        self._try_match()

    def _on_right(self, btn: QPushButton) -> None:
        if self._selected_right is btn:
            self._deselect_right()
            return
        self._deselect_right()
        self._selected_right = btn
        btn.setObjectName("btnChoiceSelected")
        btn.setStyle(btn.style())
        self._try_match()

    def _deselect_left(self) -> None:
        if self._selected_left is not None:
            self._selected_left.setObjectName("btnChoice")
            self._selected_left.setStyle(self._selected_left.style())
            self._selected_left = None

    def _deselect_right(self) -> None:
        if self._selected_right is not None:
            self._selected_right.setObjectName("btnChoice")
            self._selected_right.setStyle(self._selected_right.style())
            self._selected_right = None

    def _try_match(self) -> None:
        if self._selected_left is None or self._selected_right is None:
            return

        lid = self._id_of_left[self._selected_left]
        rid = self._id_of_right[self._selected_right]
        lb, rb = self._selected_left, self._selected_right
        self._selected_left = None
        self._selected_right = None

        if lid == rid:
            for btn in (lb, rb):
                btn.setObjectName("btnChoiceCorrect")
                btn.setStyle(btn.style())
                btn.setEnabled(False)
            self._matched += 1
            if self._matched == 6:
                result = self._errors == 0
                QTimer.singleShot(600, lambda: self._on_answer(result))
        else:
            self._errors += 1
            for btn in (lb, rb):
                btn.setObjectName("btnChoiceWrong")
                btn.setStyle(btn.style())

            def _reset(b1=lb, b2=rb):
                for b in (b1, b2):
                    if b.isEnabled():
                        b.setObjectName("btnChoice")
                        b.setStyle(b.style())

            QTimer.singleShot(700, _reset)


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

        self._mode_stack = QStackedWidget()

        self._anki = AnkiFlipWidget(on_answer=self._on_answered)
        self._multi = MultiChoiceWidget(on_answer=self._on_answered)
        self._fill_blank = FillBlankWidget(on_answer=self._on_answered)
        self._matching = MatchingWidget(on_answer=self._on_matching_answered)

        self._mode_stack.addWidget(self._anki)        # 0
        self._mode_stack.addWidget(self._multi)       # 1
        self._mode_stack.addWidget(self._fill_blank)  # 2
        self._mode_stack.addWidget(self._matching)    # 3

        self._exercise_count: int = 0
        self._in_matching: bool = False

        root.addWidget(self._mode_stack, stretch=1)

    def begin(self):
        """Вызвать перед показом экрана — загружает первую карточку."""
        self._exercise_count = 0
        self._in_matching = False
        self._show_current()

    def _on_matching_answered(self, correct: bool):
        """Матчинг завершён — не тратит карточку из очереди."""
        self._engine.submit_additional_results(
            self._matching.used_element_ids(),
            correct,
        )
        self._in_matching = False
        QTimer.singleShot(80, self._show_current)

    def _show_current(self):
        card = self._engine.current_card()
        if card is None:
            self._on_finish()
            return

        pos, total = self._engine.progress_tuple()
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(pos - 1)
        self._counter_label.setText(f"{pos} / {total}")

        self._exercise_count += 1
        if not self._in_matching and self._exercise_count > 1:
            if random.random() < 1 / 20:
                matching_pool = self._engine.get_matching_cards(card, count=6)
                if len(matching_pool) >= 6:
                    self._in_matching = True
                    self._mode_stack.setCurrentIndex(3)
                    self._matching.load(matching_pool)
                    return

        self._in_matching = False

        available_modes = ["anki"]
        distractors = self._engine.get_distractors(card, count=3)
        if len(distractors) >= 1:
            available_modes.append("multi")
        if card.kind == "construction" and getattr(card, "has_element_tag", False):
            available_modes.append("fill_blank")

        chosen_mode = random.choice(available_modes)
        reverse_direction = random.random() < 0.5

        if chosen_mode == "fill_blank":
            self._mode_stack.setCurrentIndex(2)
            self._fill_blank.load(card)
        elif chosen_mode == "multi":
            self._mode_stack.setCurrentIndex(1)
            self._multi.load(card, distractors, reverse=reverse_direction)
        else:
            self._mode_stack.setCurrentIndex(0)
            self._anki.load(card, reverse=reverse_direction)

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
