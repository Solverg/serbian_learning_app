# Serbian Flashcards

Приложение для изучения сербского языка на Windows (PyQt6).

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
│   ├── card_widget.py       # экран карточки (Anki-flip + multiple choice + fill in the blank)
│   └── results_screen.py    # итоги сессии
├── data/
│   ├── serbian_words.xml        # словарь слов
│   ├── serbian_constructions.xml # словарь конструкций
│   ├── progress_words.json      # прогресс по словам
│   └── progress_constructions.json # прогресс по конструкциям
└── assets/
    └── style_dark.qss       # тёмная тема
```

## Режимы обучения
- **Anki-flip**: показать карточку → открыть ответ → отметить «Знаю / Не знаю».
- **Multiple choice**: выбрать правильный вариант из 4 кнопок.
- **Fill in the blank**: по переводу и фразе с пропуском ввести недостающее слово.
- Для каждой карточки направление выбирается случайно:
  - **прямое**: сербский → русский;
  - **обратное**: русский → сербский.

Роутинг режимов теперь динамический:
- **Anki-flip** доступен всегда;
- **Multiple choice** доступен при наличии хотя бы одного дистрактора;
- **Fill in the blank** доступен только для конструкций, где в XML есть тег `<element>` и фраза состоит более чем из одного слова.

## Формат словаря (XML)
```xml
<vocabulary>
    <word>
        <element_id>word_1</element_id>
        <element>Немати</element>
        <text>не́мати</text>
        <phonetic_transcription>[ˈnɛmati]</phonetic_transcription>
        <pronunciation_description>не́-ма-ти</pronunciation_description>
        <translation>Не иметь</translation>
        <note>Заметка</note>
    </word>
</vocabulary>
```

Поле `<element>` — новый формат отображаемого сербского текста.  
Если `<element>` отсутствует или пустой, приложение использует `<text>`.

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
