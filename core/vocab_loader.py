from pathlib import Path
import logging
from lxml import etree
from core.models import Card

logger = logging.getLogger(__name__)


def _text(el: etree._Element, tag: str) -> str:
    """Безопасно достаёт текст дочернего тега, возвращает '' если нет."""
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _text_with_fallback(el: etree._Element, preferred_tag: str, fallback_tag: str) -> str:
    """Возвращает preferred_tag, а если он пуст — fallback_tag."""
    value = _text(el, preferred_tag)
    return value if value else _text(el, fallback_tag)


def load_words(xml_path: Path) -> list[Card]:
    """Загружает все <word> из serbian_words.xml."""
    try:
        tree = etree.parse(str(xml_path))
    except (OSError, etree.XMLSyntaxError) as exc:
        logger.exception("Не удалось загрузить words XML '%s': %s", xml_path, exc)
        return []

    cards = []
    for word in tree.findall("word"):
        cards.append(Card(
            element_id=_text(word, "element_id"),
            kind="word",
            text=_text_with_fallback(word, "element", "text"),
            translation=_text(word, "translation"),
            phonetic_transcription=_text(word, "phonetic_transcription"),
            pronunciation_description=_text(word, "pronunciation_description"),
            note=_text(word, "note"),
        ))
    return cards


def load_constructions(xml_path: Path) -> list[Card]:
    """Загружает все <construction> из serbian_constructions.xml."""
    try:
        tree = etree.parse(str(xml_path))
    except (OSError, etree.XMLSyntaxError) as exc:
        logger.exception("Не удалось загрузить constructions XML '%s': %s", xml_path, exc)
        return []

    cards = []
    for construction in tree.findall("construction"):
        element_node = construction.find("element")
        text_val = _text_with_fallback(construction, "element", "text")
        is_eligible = (element_node is not None) and (len(text_val.split()) > 1)

        cards.append(Card(
            element_id=_text(construction, "element_id"),
            kind="construction",
            text=text_val,
            translation=_text(construction, "translation"),
            phonetic_transcription=_text(construction, "phonetic_transcription"),
            pronunciation_description=_text(construction, "pronunciation_description"),
            note=_text(construction, "note"),
            has_element_tag=is_eligible,
        ))
    return cards


def load_all(data_dir: Path) -> list[Card]:
    """Загружает слова и конструкции из папки data/."""
    words = load_words(data_dir / "serbian_words.xml")
    constructions = load_constructions(data_dir / "serbian_constructions.xml")
    return words + constructions
