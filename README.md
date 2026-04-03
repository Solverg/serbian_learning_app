# Serbian Flashcards

Приложение для изучения сербского языка на Windows.

## Стек
- Python 3.11+
- PyQt6
- lxml
- PyInstaller (сборка в .exe)

## Структура
```
serbian_flashcards/
├── main.py                  # точка входа
├── core/
│   ├── models.py            # Card, ProgressEntry
│   ├── vocab_loader.py      # парсинг XML словарей
│   ├── progress_store.py    # чтение/запись JSON прогресса
│   └── session_engine.py    # алгоритм отбора карточек
├── ui/
│   ├── main_window.py       # главное окно, навигация
│   ├── deck_selector.py     # выбор режима и размера сессии
│   ├── card_widget.py       # экран карточки (Anki-flip + multiple choice)
│   └── results_screen.py    # итоги сессии
├── data/
│   ├── serbian_words.xml        # словарь слов
│   ├── serbian_constructions.xml # словарь конструкций
│   ├── progress_words.json      # прогресс по словам
│   └── progress_constructions.json # прогресс по конструкциям
└── assets/
    └── style_dark.qss       # тёмная тема
```

## Формат словаря (XML)
```xml
<vocabulary>
    <word>
        <element_id>word_1</element_id>
        <text>не́мати</text>
        <phonetic_transcription>[ˈnɛmati]</phonetic_transcription>
        <pronunciation_description>не́-ма-ти</pronunciation_description>
        <translation>Не иметь</translation>
        <note>Заметка</note>
    </word>
</vocabulary>
```

## Формат прогресса (JSON)
```json
{
  "elements": [
    {"element_id": "word_1", "errors": 0, "repetitions": 5, "last_practiced": "2026-04-01"}
  ]
}
```

## Запуск (dev)
```
pip install -r requirements.txt
python main.py
```

## Сборка .exe
```
build.bat
```

## Тесты
```
python test_loader.py
python test_progress.py
python test_session.py
```
