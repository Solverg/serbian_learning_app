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
    """Полный цикл сессии: старт → ответы → финиш → проверка файлов."""
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

        assert len(engine._queue) == 4
        print(f"  ✓ Очередь сформирована: {len(engine._queue)} карточек")
        print(f"    Порядок: {[c.element_id for c in engine._queue]}")

        # Пройти все карточки: 3 правильных, 1 ошибка
        answers = [True, True, False, True]
        while not engine.is_finished():
            card = engine.current_card()
            idx = engine._current_index
            engine.submit_answer(answers[idx])

        assert engine.is_finished()

        stats = engine.finish_session()
        print(f"  ✓ finish_session: total={stats.total}, correct={stats.correct}, errors={stats.errors}")
        print(f"    accuracy={stats.accuracy:.0%}")
        assert stats.total == 4
        assert stats.correct == 3
        assert stats.errors == 1
        assert 0.0 <= stats.accuracy <= 1.0

        # Проверить что файлы прогресса обновились
        words_prog = load_progress(tmp / "progress_words.json")
        constr_prog = load_progress(tmp / "progress_constructions.json")

        for eid, entry in {**words_prog, **constr_prog}.items():
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
        assert first.element_id == "construction_108", \
            f"Новая карточка должна быть первой, получили {first.element_id}"
        print(f"  ✓ Новая карточка идёт первой: {first.element_id}")

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
        assert pos == 1 and total == 4

        engine.submit_answer(True)
        pos, total = engine.progress_tuple()
        assert pos == 2 and total == 4
        print(f"  ✓ progress_tuple: после 1 ответа → ({pos}/{total})")


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

    print("\n✓ Все тесты прошли\n")
