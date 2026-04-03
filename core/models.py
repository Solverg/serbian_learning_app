from dataclasses import dataclass, field
from datetime import date
from typing import Literal


@dataclass
class Card:
    """Одна карточка — слово или конструкция из XML-словаря."""
    element_id: str                          # "word_325" / "construction_108"
    kind: Literal["word", "construction"]    # тип элемента
    text: str                                # сербский текст (кириллица)
    translation: str                         # перевод на русский
    phonetic_transcription: str = ""         # МФА: [ˈnɛmati]
    pronunciation_description: str = ""      # русскоязычная подсказка произношения
    note: str = ""                           # дополнительная заметка


@dataclass
class ProgressEntry:
    """Запись прогресса для одного элемента из progress_*.json."""
    element_id: str
    errors: int = 0
    repetitions: int = 0
    last_practiced: date = field(default_factory=date.today)

    def error_rate(self) -> float:
        """Доля ошибок. 0.0 если повторений не было."""
        if self.repetitions == 0:
            return 0.0
        return self.errors / self.repetitions

    def is_new(self) -> bool:
        return self.repetitions == 0
