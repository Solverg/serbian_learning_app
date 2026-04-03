"""
Точка входа приложения Serbian Flashcards.
"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from core.session_engine import SessionEngine
from ui.main_window import MainWindow

# Пути к данным — рядом с main.py (работает и в dev, и в .exe через PyInstaller)
BASE_DIR     = Path(__file__).parent
DATA_DIR     = BASE_DIR / "data"
PROGRESS_DIR = BASE_DIR / "data"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Serbian Flashcards")

    # Загрузить тему
    qss_path = BASE_DIR / "assets" / "style_dark.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    # Инициализировать движок
    engine = SessionEngine(DATA_DIR, PROGRESS_DIR)
    engine.load_vocab()

    # Запустить окно
    window = MainWindow(engine)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
