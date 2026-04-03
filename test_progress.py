"""
Тест progress_store: чтение, обновление, атомарная запись, round-trip.
"""
import sys
import json
import tempfile
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent))

from core.models import ProgressEntry
from core.progress_store import load_progress, save_progress, apply_session_results

# ---------- фикстура: содержимое файла в твоём формате ----------
SAMPLE = {
    "elements": [
        {"element_id": "word_325",        "errors": 0, "repetitions": 5,  "last_practiced": "2025-10-02"},
        {"element_id": "word_326",        "errors": 2, "repetitions": 8,  "last_practiced": "2026-01-15"},
        {"element_id": "construction_108","errors": 0, "repetitions": 0,  "last_practiced": "2026-02-09"},
        {"element_id": "construction_109","errors": 1, "repetitions": 3,  "last_practiced": "2025-12-20"},
    ]
}


def test_load():
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(SAMPLE, f, ensure_ascii=False)
        tmp = Path(f.name)

    entries = load_progress(tmp)
    assert len(entries) == 4

    w = entries["word_325"]
    assert w.repetitions == 5
    assert w.errors == 0
    assert w.last_practiced == date(2025, 10, 2)
    assert w.is_new() is False
    assert w.error_rate() == 0.0

    w2 = entries["word_326"]
    assert w2.error_rate() == 2 / 8

    c = entries["construction_108"]
    assert c.is_new() is True
    assert c.error_rate() == 0.0

    tmp.unlink()
    print("  ✓ load_progress: все поля читаются корректно")
    print(f"    word_325: repetitions={w.repetitions}, last_practiced={w.last_practiced}")
    print(f"    word_326: error_rate={w2.error_rate():.3f}")
    print(f"    construction_108: is_new={c.is_new()}")


def test_missing_file():
    entries = load_progress(Path("/tmp/nonexistent_XYZZY.json"))
    assert entries == {}
    print("  ✓ load_progress: несуществующий файл → пустой dict")


def test_save_and_reload():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "progress_test.json"

        entries = {
            "word_325": ProgressEntry("word_325", errors=1, repetitions=6,
                                       last_practiced=date(2026, 3, 1)),
            "construction_108": ProgressEntry("construction_108", errors=0, repetitions=2,
                                               last_practiced=date(2026, 3, 15)),
        }

        save_progress(path, entries)
        assert path.exists()
        assert not path.with_suffix(".tmp").exists()  # tmp должен быть удалён

        reloaded = load_progress(path)
        assert len(reloaded) == 2

        r = reloaded["word_325"]
        assert r.errors == 1
        assert r.repetitions == 6
        assert r.last_practiced == date(2026, 3, 1)

        print("  ✓ save_progress + reload: round-trip без потерь")
        print(f"    word_325: errors={r.errors}, repetitions={r.repetitions}, last_practiced={r.last_practiced}")


def test_apply_session():
    entries: dict = {}

    # Первая сессия: word_325 — правильно, word_326 — ошибка
    apply_session_results(entries, [
        ("word_325", True),
        ("word_326", False),
        ("word_325", True),   # повторяется в одной сессии
    ], today=date(2026, 4, 1))

    assert entries["word_325"].repetitions == 2
    assert entries["word_325"].errors == 0
    assert entries["word_325"].last_practiced == date(2026, 4, 1)

    assert entries["word_326"].repetitions == 1
    assert entries["word_326"].errors == 1

    # Новый элемент создаётся автоматически
    assert "word_326" in entries

    print("  ✓ apply_session_results: счётчики обновляются верно")
    print(f"    word_325: rep={entries['word_325'].repetitions}, err={entries['word_325'].errors}")
    print(f"    word_326: rep={entries['word_326'].repetitions}, err={entries['word_326'].errors}")


if __name__ == "__main__":
    print("\n=== Тест: progress_store ===\n")
    print("[ Чтение ]")
    test_load()
    test_missing_file()
    print("\n[ Запись / round-trip ]")
    test_save_and_reload()
    print("\n[ Обновление после сессии ]")
    test_apply_session()
    print("\n✓ Все тесты прошли\n")
