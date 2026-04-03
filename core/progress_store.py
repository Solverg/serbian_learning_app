"""
Чтение и запись файлов прогресса progress_words.json / progress_constructions.json.

Формат файла:
{
  "elements": [
    {"element_id": "word_1", "errors": 0, "repetitions": 5, "last_practiced": "2025-10-02"},
    ...
  ]
}

Атомарная запись: сначала во временный файл рядом, потом os.replace() —
если процесс упадёт в середине записи, старый файл останется целым.
"""

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path

from core.models import ProgressEntry

logger = logging.getLogger(__name__)


# ---------- чтение ----------

def load_progress(json_path: Path) -> dict[str, ProgressEntry]:
    """
    Читает файл прогресса и возвращает словарь {element_id: ProgressEntry}.
    Если файл не существует — возвращает пустой словарь (новый пользователь).
    """
    if not json_path.exists():
        return {}

    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        _backup_corrupt_file(json_path)
        logger.exception("Не удалось прочитать файл прогресса '%s': %s", json_path, exc)
        return {}

    if not isinstance(data, dict):
        logger.warning(
            "Некорректный формат файла прогресса '%s': ожидался JSON-объект, получено %s",
            json_path,
            type(data).__name__,
        )
        return {}

    result: dict[str, ProgressEntry] = {}
    elements = data.get("elements", [])
    if not isinstance(elements, list):
        logger.warning("Некорректный формат поля 'elements' в '%s': ожидается список", json_path)
        return {}

    for item in elements:
        if not isinstance(item, dict) or "element_id" not in item:
            logger.warning("Пропущена некорректная запись прогресса в '%s': %r", json_path, item)
            continue
        eid = item["element_id"]
        result[eid] = ProgressEntry(
            element_id=eid,
            errors=item.get("errors", 0),
            repetitions=item.get("repetitions", 0),
            last_practiced=_parse_date(item.get("last_practiced")),
        )
    return result


def _parse_date(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        logger.warning("Некорректный формат даты в прогрессе: %r. Используется текущая дата.", value)
        return date.today()


def _backup_corrupt_file(json_path: Path) -> None:
    """Создаёт резервную копию повреждённого файла прогресса рядом с оригиналом."""
    if not json_path.exists():
        return
    backup_path = json_path.with_name(f"{json_path.name}.corrupt.{datetime.now().strftime('%Y%m%d%H%M%S')}")
    try:
        os.replace(json_path, backup_path)
        logger.warning("Повреждённый файл прогресса перемещён в '%s'", backup_path)
    except OSError as exc:
        logger.exception("Не удалось создать backup повреждённого файла '%s': %s", json_path, exc)


# ---------- запись ----------

def save_progress(json_path: Path, entries: dict[str, ProgressEntry]) -> None:
    """
    Атомарно сохраняет словарь прогресса в файл.
    Порядок элементов сохраняется по element_id (для читаемости diff'ов).
    """
    data = {
        "elements": [
            {
                "element_id": e.element_id,
                "errors": e.errors,
                "repetitions": e.repetitions,
                "last_practiced": e.last_practiced.strftime("%Y-%m-%d"),
            }
            for e in sorted(entries.values(), key=_sort_key)
        ]
    }

    tmp_path = json_path.with_name(json_path.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    os.replace(tmp_path, json_path)  # атомарная замена


def _sort_key(e: ProgressEntry) -> tuple:
    """Сортировка: сначала по типу (word/construction), потом по числовому id."""
    eid = e.element_id  # "word_325" / "construction_108"
    parts = eid.rsplit("_", 1)
    prefix = parts[0] if len(parts) == 2 else eid
    number = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 0
    return (prefix, number)


# ---------- обновление после сессии ----------

def apply_session_results(
    entries: dict[str, ProgressEntry],
    results: list[tuple[str, bool]],  # [(element_id, was_correct), ...]
    today: date | None = None,
) -> None:
    """
    Обновляет записи прогресса по итогам сессии.
    Изменяет entries на месте (in-place).

    results: список пар (element_id, was_correct)
    today: дата тренировки (по умолчанию — сегодня)
    """
    practiced_date = today or date.today()

    for element_id, was_correct in results:
        if element_id not in entries:
            entries[element_id] = ProgressEntry(element_id=element_id)

        entry = entries[element_id]
        entry.repetitions += 1
        if not was_correct:
            entry.errors += 1
        entry.last_practiced = practiced_date
