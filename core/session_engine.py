"""
Session engine — отбор карточек и управление сессией.

Приоритет отбора (по убыванию важности):
  1. Новые карточки (repetitions == 0)
  2. Давно не тренировавшиеся (наибольший days_since_practiced)
  3. Проблемные (высокий error_rate = errors / repetitions)

Внутри каждой приоритетной группы — случайный порядок.
Результаты хранятся в памяти, в файл идут только через progress_store.
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

from core.models import Card, ProgressEntry
from core.progress_store import (
    apply_session_results,
    load_progress,
    save_progress,
)
from core.vocab_loader import load_all

logger = logging.getLogger(__name__)


# ---------- типы ----------

DeckMode = Literal["words", "constructions", "mixed"]


@dataclass
class SessionResult:
    """Итог одной попытки ответа на карточку."""
    element_id: str
    was_correct: bool


@dataclass
class SessionStats:
    """Статистика сессии для экрана результатов."""
    total: int
    correct: int
    errors: int
    error_cards: list[Card] = field(default_factory=list)  # карточки с ошибками

    @property
    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        return self.correct / self.total


# ---------- движок ----------

class SessionEngine:
    """
    Управляет одной учебной сессией.

    Использование:
        engine = SessionEngine(data_dir, progress_dir)
        engine.start_session(mode="mixed", session_size=20)

        while not engine.is_finished():
            card = engine.current_card()
            # показать карточку пользователю ...
            engine.submit_answer(was_correct=True)

        stats = engine.finish_session()
        # stats содержит итоги; progress записан в файлы
    """

    def __init__(self, data_dir: Path, progress_dir: Path):
        self._data_dir = data_dir
        self._progress_dir = progress_dir

        # Кэш всех карточек (загружается один раз)
        self._all_cards: dict[str, Card] = {}

        # Прогресс (загружается при старте сессии)
        self._progress_words: dict[str, ProgressEntry] = {}
        self._progress_constructions: dict[str, ProgressEntry] = {}

        # Очередь текущей сессии
        self._queue: list[Card] = []
        self._current_index: int = 0
        self._results: list[SessionResult] = []
        self._stats: SessionStats | None = None
        self._progress_saved: bool = False

    # ---------- публичный API ----------

    def load_vocab(self) -> None:
        """Загрузить словари с диска. Вызывать один раз при старте приложения."""
        cards = load_all(self._data_dir)
        self._all_cards = {c.element_id: c for c in cards}

    def start_session(
        self,
        mode: DeckMode = "mixed",
        session_size: int = 20,
        today: date | None = None,
    ) -> None:
        """
        Подготовить очередь карточек для новой сессии.
        Загружает актуальный прогресс с диска перед каждой сессией.
        """
        self._today = today or date.today()

        # Загрузить свежий прогресс
        self._progress_words = load_progress(
            self._progress_dir / "progress_words.json"
        )
        self._progress_constructions = load_progress(
            self._progress_dir / "progress_constructions.json"
        )

        # Отобрать карточки по режиму
        candidates = self._get_candidates(mode)

        # Отсортировать по приоритету и взять session_size
        ranked = self._rank(candidates)
        self._queue = ranked[:session_size]

        self._current_index = 0
        self._results = []
        self._stats = None
        self._progress_saved = False

    def current_card(self) -> Card | None:
        """Текущая карточка. None если сессия завершена."""
        if self.is_finished():
            return None
        return self._queue[self._current_index]

    def submit_answer(self, was_correct: bool) -> None:
        """Зафиксировать ответ на текущую карточку и перейти к следующей."""
        if self.is_finished():
            return
        card = self._queue[self._current_index]
        self._results.append(SessionResult(card.element_id, was_correct))
        self._current_index += 1

    def is_finished(self) -> bool:
        return self._current_index >= len(self._queue)

    def progress_tuple(self) -> tuple[int, int]:
        """(текущий номер, всего) для прогресс-бара."""
        return (self._current_index + 1, len(self._queue))

    def finish_session(self) -> SessionStats:
        """
        Завершить сессию и вернуть статистику.
        Сохранение прогресса выполняется отдельно (по кнопке пользователя).
        Безопасно вызывать только после is_finished() == True.
        """
        if self._stats is not None:
            return self._stats

        correct = sum(1 for r in self._results if r.was_correct)
        error_ids = {r.element_id for r in self._results if not r.was_correct}
        error_cards = [self._all_cards[eid] for eid in error_ids if eid in self._all_cards]

        self._stats = SessionStats(
            total=len(self._results),
            correct=correct,
            errors=len(error_ids),
            error_cards=error_cards,
        )
        return self._stats

    def save_session_progress(self) -> tuple[bool, str]:
        """
        Сохранить прогресс завершённой сессии в JSON-файлы.
        Возвращает (успех, сообщение для UI). После записи выполняется верификация.
        """
        if not self.is_finished():
            return (False, "Сессия ещё не завершена.")
        if self._progress_saved:
            return (True, "Прогресс уже сохранён.")

        word_results, construction_results = self._split_results_by_kind()
        word_ids = {element_id for element_id, _ in word_results}
        construction_ids = {element_id for element_id, _ in construction_results}

        try:
            if word_results:
                apply_session_results(self._progress_words, word_results, self._today)
                words_path = self._progress_dir / "progress_words.json"
                save_progress(words_path, self._progress_words)
                self._verify_saved_entries(words_path, self._progress_words, word_ids)

            if construction_results:
                apply_session_results(
                    self._progress_constructions, construction_results, self._today
                )
                constructions_path = self._progress_dir / "progress_constructions.json"
                save_progress(constructions_path, self._progress_constructions)
                self._verify_saved_entries(
                    constructions_path,
                    self._progress_constructions,
                    construction_ids,
                )
        except Exception as exc:
            logger.exception("Ошибка сохранения прогресса: %s", exc)
            return (False, "Не удалось сохранить прогресс. Проверьте логи приложения.")

        self._progress_saved = True
        return (True, "Прогресс успешно сохранён.")

    @staticmethod
    def _verify_saved_entries(
        path: Path,
        expected_store: dict[str, ProgressEntry],
        touched_ids: set[str],
    ) -> None:
        """Проверка после записи: значения в файле совпадают с ожиданиями."""
        reloaded = load_progress(path)
        missing = touched_ids - set(reloaded.keys())
        if missing:
            raise ValueError(f"После сохранения отсутствуют элементы: {sorted(missing)}")

        for element_id in touched_ids:
            actual = reloaded[element_id]
            expected = expected_store[element_id]
            if (
                actual.errors != expected.errors
                or actual.repetitions != expected.repetitions
                or actual.last_practiced != expected.last_practiced
            ):
                raise ValueError(
                    f"Верификация не пройдена для {element_id}: "
                    f"actual=({actual.errors}, {actual.repetitions}, {actual.last_practiced}) "
                    f"expected=({expected.errors}, {expected.repetitions}, {expected.last_practiced})"
                )

    def _split_results_by_kind(self) -> tuple[list[tuple[str, bool]], list[tuple[str, bool]]]:
        word_results: list[tuple[str, bool]] = []
        construction_results: list[tuple[str, bool]] = []
        for r in self._results:
            card = self._all_cards.get(r.element_id)
            if card and card.kind == "word":
                word_results.append((r.element_id, r.was_correct))
            else:
                construction_results.append((r.element_id, r.was_correct))
        return word_results, construction_results

    def get_distractors(self, card: Card, count: int = 3) -> list[Card]:
        """
        Вернуть `count` случайных карточек того же типа для multiple choice.
        Исключает текущую карточку.
        """
        same_kind = [
            c for c in self._all_cards.values()
            if c.kind == card.kind and c.element_id != card.element_id
        ]
        return random.sample(same_kind, min(count, len(same_kind)))

    # ---------- внутренние методы ----------

    def _get_candidates(self, mode: DeckMode) -> list[Card]:
        if mode == "words":
            return [c for c in self._all_cards.values() if c.kind == "word"]
        if mode == "constructions":
            return [c for c in self._all_cards.values() if c.kind == "construction"]
        return list(self._all_cards.values())

    def _rank(self, candidates: list[Card]) -> list[Card]:
        """
        Разбить на три приоритетные группы, внутри каждой — случайный порядок,
        затем склеить: новые → старые → проблемные.
        """
        new: list[Card] = []
        old: list[Card] = []
        problematic: list[Card] = []

        for card in candidates:
            entry = self._get_entry(card)
            if entry.is_new():
                new.append(card)
            elif self._days_since(entry) >= 1:
                old.append(card)
            else:
                problematic.append(card)

        # Внутри группы «старые» — сортировка по давности (самые старые первыми),
        # при равенстве — по error_rate убывающе
        old.sort(key=lambda c: (
            -self._days_since(self._get_entry(c)),
            -self._get_entry(c).error_rate(),
        ))

        # Внутри «проблемных» — по error_rate убывающе
        problematic.sort(key=lambda c: -self._get_entry(c).error_rate())

        # Новые и проблемные перемешать внутри своей группы
        random.shuffle(new)
        random.shuffle(problematic)

        return new + old + problematic

    def _get_entry(self, card: Card) -> ProgressEntry:
        """Вернуть запись прогресса или пустую заглушку если карточки нет в прогрессе."""
        store = (
            self._progress_words
            if card.kind == "word"
            else self._progress_constructions
        )
        return store.get(card.element_id, ProgressEntry(card.element_id))

    def _days_since(self, entry: ProgressEntry) -> int:
        return (self._today - entry.last_practiced).days
