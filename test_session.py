"""
Тест session_engine: отбор карточек, приоритеты, управление очередью,
финальная запись прогресса.
"""
import sys
import json
import tempfile
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent))

from core.session_engine import SessionEngine
from core.progress_store import load_progress

DATA_DIR = Path(__file__).parent / "data"


def make_progress_dir(tmp: Path, words: list[dict], constructions: list[dict]) -> None:
    """Создать progress_*.json в tmp-папке."""
    (tmp / "progress_words.json").write_text(
        json.dumps({"elements": words}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    (tmp / "progress_constructions.json").write_text(
        json.dumps({"elements": constructions}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def test_basic_session():
    """Полный цикл сессии: старт → ответы → финиш → явное сохранение → проверка файлов."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        make_progress_dir(tmp,
            words=[
                {"element_id": "word_325", "errors": 0, "repetitions": 3, "last_practiced": "2025-10-01"},
                {"element_id": "word_326", "errors": 2, "repetitions": 4, "last_practiced": "2026-01-01"},
            ],
            constructions=[
                {"element_id": "construction_108", "errors": 0, "repetitions": 0, "last_practiced": "2026-01-01"},
                {"element_id": "construction_109", "errors": 1, "repetitions": 2, "last_practiced": "2025-12-01"},
            ]
        )

        engine = SessionEngine(DATA_DIR, tmp)
        engine.load_vocab()
        engine.start_session(mode="mixed", session_size=4, today=date(2026, 4, 1))

        assert len(engine._queue) == 20
        print(f"  ✓ Очередь сформирована: {len(engine._queue)} карточек")
        print(f"    Порядок: {[c.element_id for c in engine._queue]}")

        # Пройти все карточки: 1 ошибка
        answers = [True] * len(engine._queue)
        answers[2] = False
        while not engine.is_finished():
            card = engine.current_card()
            idx = engine._current_index
            engine.submit_answer(answers[idx])

        assert engine.is_finished()

        stats = engine.finish_session()
        print(f"  ✓ finish_session: total={stats.total}, correct={stats.correct}, errors={stats.errors}")
        print(f"    accuracy={stats.accuracy:.0%}")
        assert stats.total == 20
        assert stats.correct == 19
        assert stats.errors == 1
        assert 0.0 <= stats.accuracy <= 1.0

        # До явного сохранения файлы не должны меняться
        words_before_save = load_progress(tmp / "progress_words.json")
        assert words_before_save["word_325"].last_practiced == date(2025, 10, 1)
        print("  ✓ До нажатия кнопки сохранения прогресс в файле не меняется")

        saved, message = engine.save_session_progress()
        assert saved is True, message
        print(f"  ✓ save_session_progress: {message}")

        # Проверить что файлы прогресса обновились
        words_prog = load_progress(tmp / "progress_words.json")
        constr_prog = load_progress(tmp / "progress_constructions.json")

        practiced_ids = {result.element_id for result in engine._results}
        for eid in practiced_ids:
            entry = words_prog.get(eid) or constr_prog.get(eid)
            assert entry is not None, f"{eid}: запись не найдена после сохранения"
            assert entry.last_practiced == date(2026, 4, 1), \
                f"{eid}: last_practiced не обновился"
            assert entry.repetitions > 0, f"{eid}: repetitions не увеличился"

        print(f"  ✓ Файлы прогресса обновлены, last_practiced=2026-04-01")


def test_priority_order():
    """Новые карточки должны идти первыми."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # construction_108 — новая (repetitions=0), остальные — нет
        make_progress_dir(tmp,
            words=[
                {"element_id": "word_325", "errors": 0, "repetitions": 5, "last_practiced": "2026-03-30"},
                {"element_id": "word_326", "errors": 0, "repetitions": 3, "last_practiced": "2026-03-31"},
            ],
            constructions=[
                {"element_id": "construction_108", "errors": 0, "repetitions": 0, "last_practiced": "2026-01-01"},
                {"element_id": "construction_109", "errors": 0, "repetitions": 1, "last_practiced": "2026-03-29"},
            ]
        )

        engine = SessionEngine(DATA_DIR, tmp)
        engine.load_vocab()
        engine.start_session(mode="mixed", session_size=4, today=date(2026, 4, 1))

        first = engine._queue[0]
        first_entry = engine._get_entry(first)
        assert first_entry.is_new(), \
            f"Первой должна быть новая карточка, получили {first.element_id} (repetitions={first_entry.repetitions})"
        print(f"  ✓ В начале очереди новая карточка: {first.element_id}")

        order = [c.element_id for c in engine._queue]
        print(f"    Полный порядок: {order}")


def test_mode_filter():
    """Режим 'words' — только слова, 'constructions' — только конструкции."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        make_progress_dir(tmp, words=[], constructions=[])

        engine = SessionEngine(DATA_DIR, tmp)
        engine.load_vocab()

        engine.start_session(mode="words", session_size=10, today=date(2026, 4, 1))
        assert all(c.kind == "word" for c in engine._queue)
        print(f"  ✓ mode='words': {len(engine._queue)} карточек, все kind=word")

        engine.start_session(mode="constructions", session_size=10, today=date(2026, 4, 1))
        assert all(c.kind == "construction" for c in engine._queue)
        print(f"  ✓ mode='constructions': {len(engine._queue)} карточек, все kind=construction")


def test_distractors():
    """get_distractors не возвращает текущую карточку, нужное количество."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        make_progress_dir(tmp, words=[], constructions=[])

        engine = SessionEngine(DATA_DIR, tmp)
        engine.load_vocab()
        engine.start_session(mode="mixed", session_size=4, today=date(2026, 4, 1))

        card = engine.current_card()
        distractors = engine.get_distractors(card, count=3)
        assert card not in distractors
        assert len(distractors) <= 3
        assert all(d.kind == card.kind for d in distractors)
        print(f"  ✓ get_distractors: {len(distractors)} дистрактора(ов), тип совпадает, текущая карточка исключена")


def test_progress_bar():
    """progress_tuple корректно считает позицию."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        make_progress_dir(tmp, words=[], constructions=[])

        engine = SessionEngine(DATA_DIR, tmp)
        engine.load_vocab()
        engine.start_session(mode="mixed", session_size=4, today=date(2026, 4, 1))

        pos, total = engine.progress_tuple()
        assert pos == 1 and total == 20

        engine.submit_answer(True)
        pos, total = engine.progress_tuple()
        assert pos == 2 and total == 20
        print(f"  ✓ progress_tuple: после 1 ответа → ({pos}/{total})")


def test_matching_progress_saved():
    """Дополнительные результаты (matching) сохраняются в прогресс."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        make_progress_dir(tmp, words=[], constructions=[])

        engine = SessionEngine(DATA_DIR, tmp)
        engine.load_vocab()
        engine.start_session(mode="mixed", session_size=20, today=date(2026, 4, 1))

        card = engine.current_card()
        matching_cards = engine.get_matching_cards(card, count=6)
        ids = [c.element_id for c in matching_cards]
        engine.submit_additional_results(ids, was_correct=False)

        while not engine.is_finished():
            engine.submit_answer(True)

        saved, message = engine.save_session_progress()
        assert saved is True, message

        words_prog = load_progress(tmp / "progress_words.json")
        constr_prog = load_progress(tmp / "progress_constructions.json")
        for eid in ids:
            entry = words_prog.get(eid) or constr_prog.get(eid)
            assert entry is not None, f"{eid}: запись не найдена после сохранения"
            assert entry.last_practiced == date(2026, 4, 1)
        print("  ✓ matching-результаты попали в сохранённый прогресс")


if __name__ == "__main__":
    print("\n=== Тест: session_engine ===\n")

    print("[ Полный цикл сессии ]")
    test_basic_session()

    print("\n[ Приоритет новых карточек ]")
    test_priority_order()

    print("\n[ Фильтрация по режиму ]")
    test_mode_filter()

    print("\n[ Дистракторы для multiple choice ]")
    test_distractors()

    print("\n[ Прогресс-бар ]")
    test_progress_bar()

    print("\n[ Сохранение matching ]")
    test_matching_progress_saved()

    print("\n✓ Все тесты прошли\n")
