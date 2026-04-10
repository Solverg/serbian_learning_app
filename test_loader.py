"""
Быстрый тест: убеждаемся что XML парсится корректно
и все поля читаются без потерь (включая Unicode кириллицу и МФА).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.vocab_loader import load_all, load_words, load_constructions
from core.models import Card

DATA = Path(__file__).parent / "data"


def test_words():
    cards = load_words(DATA / "serbian_words.xml")
    assert len(cards) == 2, f"Ожидалось 2 слова, получено {len(cards)}"

    w = cards[0]
    assert w.element_id == "word_325"
    assert w.kind == "word"
    assert w.text == "не́мати"
    assert w.translation == "Не иметь"
    assert "[ˈnɛmati]" in w.phonetic_transcription
    assert w.note != ""
    print(f"  ✓ word_325: '{w.text}' — {w.translation}")
    print(f"    МФА: {w.phonetic_transcription}")
    print(f"    Произношение: {w.pronunciation_description}")
    print(f"    Заметка: {w.note}")

    w2 = cards[1]
    assert w2.element_id == "word_326"
    assert "др" in w2.text
    print(f"  ✓ word_326: '{w2.text}' — {w2.translation}")


def test_constructions():
    cards = load_constructions(DATA / "serbian_constructions.xml")
    assert len(cards) == 2, f"Ожидалось 2 конструкции, получено {len(cards)}"

    c = cards[0]
    assert c.element_id == "construction_108"
    assert c.kind == "construction"
    assert "Јѐсте" in c.text
    assert c.translation == "Вы дома?"
    print(f"  ✓ construction_108: '{c.text}' — {c.translation}")

    c2 = cards[1]
    assert c2.element_id == "construction_109"
    print(f"  ✓ construction_109: '{c2.text}' — {c2.translation}")



def test_element_tag_fallback(tmp_path: Path):
    xml = tmp_path / "mixed_constructions.xml"
    xml.write_text(
        """
<root>
  <construction>
    <element_id>construction_131</element_id>
    <element>Ти си прави.</element>
    <text>Ти си пра̑ви.</text>
    <translation>Ну ты красавчик.</translation>
  </construction>
  <construction>
    <element_id>construction_132</element_id>
    <text>Старый формат.</text>
    <translation>Старый формат.</translation>
  </construction>
</root>
""".strip(),
        encoding="utf-8",
    )

    cards = load_constructions(xml)
    assert cards[0].text == "Ти си прави."
    assert cards[1].text == "Старый формат."

def test_load_all():
    all_cards = load_all(DATA)
    assert len(all_cards) == 4
    kinds = {c.kind for c in all_cards}
    assert kinds == {"word", "construction"}
    print(f"  ✓ load_all: {len(all_cards)} карточек, типы: {kinds}")


if __name__ == "__main__":
    print("\n=== Тест: models + vocab_loader ===\n")
    print("[ Слова ]")
    test_words()
    print("\n[ Конструкции ]")
    test_constructions()
    print("\n[ load_all ]")
    test_load_all()
    print("\n✓ Все тесты прошли\n")
