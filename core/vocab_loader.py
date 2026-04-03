from pathlib import Path
from lxml import etree
from core.models import Card


def _text(el: etree._Element, tag: str) -> str:
    """Безопасно достаёт текст дочернего тега, возвращает '' если нет."""
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""


def load_words(xml_path: Path) -> list[Card]:
    """Загружает все <word> из serbian_words.xml."""
    tree = etree.parse(str(xml_path))
    cards = []
    for word in tree.findall("word"):
        cards.append(Card(
            element_id=_text(word, "element_id"),
            kind="word",
            text=_text(word, "text"),
            translation=_text(word, "translation"),
            phonetic_transcription=_text(word, "phonetic_transcription"),
            pronunciation_description=_text(word, "pronunciation_description"),
            note=_text(word, "note"),
        ))
    return cards


def load_constructions(xml_path: Path) -> list[Card]:
    """Загружает все <construction> из serbian_constructions.xml."""
    tree = etree.parse(str(xml_path))
    cards = []
    for construction in tree.findall("construction"):
        cards.append(Card(
            element_id=_text(construction, "element_id"),
            kind="construction",
            text=_text(construction, "text"),
            translation=_text(construction, "translation"),
            phonetic_transcription=_text(construction, "phonetic_transcription"),
            pronunciation_description=_text(construction, "pronunciation_description"),
            note=_text(construction, "note"),
        ))
    return cards


def load_all(data_dir: Path) -> list[Card]:
    """Загружает слова и конструкции из папки data/."""
    words = load_words(data_dir / "serbian_words.xml")
    constructions = load_constructions(data_dir / "serbian_constructions.xml")
    return words + constructions
