"""
MainWindow — контейнер приложения.

Управляет переходами между экранами через QStackedWidget:
  0 — DeckSelectorScreen  (выбор режима и размера сессии)
  1 — CardScreen          (карточки)
  2 — ResultsScreen       (итоги сессии)
"""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow, QStackedWidget

from core.session_engine import DeckMode, SessionEngine

# Экраны подключаем здесь, чтобы main_window знал об их интерфейсе
# (реальный импорт будет после создания файлов)


class MainWindow(QMainWindow):

    # Индексы экранов
    SCREEN_SELECTOR = 0
    SCREEN_CARD     = 1
    SCREEN_RESULTS  = 2

    def __init__(self, engine: SessionEngine, parent=None):
        super().__init__(parent)
        self._engine = engine

        self.setWindowTitle("Serbian Flashcards")
        self.setMinimumSize(640, 520)
        self.resize(800, 620)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._build_screens()

    # ---------- построение экранов ----------

    def _build_screens(self):
        # Импортируем здесь, чтобы избежать циклических зависимостей
        from ui.deck_selector import DeckSelectorScreen
        from ui.card_widget import CardScreen
        from ui.results_screen import ResultsScreen

        self._selector = DeckSelectorScreen(on_start=self._start_session)
        self._card_screen = CardScreen(engine=self._engine, on_finish=self._show_results)
        self._results = ResultsScreen(on_restart=self._show_selector)

        self._stack.addWidget(self._selector)   # 0
        self._stack.addWidget(self._card_screen) # 1
        self._stack.addWidget(self._results)     # 2

        self._stack.setCurrentIndex(self.SCREEN_SELECTOR)

    # ---------- переходы ----------

    def _start_session(self, mode: DeckMode, session_size: int):
        """Вызывается из DeckSelectorScreen при нажатии «Начать»."""
        self._engine.start_session(mode=mode, session_size=session_size)
        self._card_screen.begin()
        self._stack.setCurrentIndex(self.SCREEN_CARD)

    def _show_results(self):
        """Вызывается из CardScreen когда очередь закончилась."""
        stats = self._engine.finish_session()
        self._results.show_stats(stats)
        self._stack.setCurrentIndex(self.SCREEN_RESULTS)

    def _show_selector(self):
        """Вызывается из ResultsScreen при нажатии «Ещё раз»."""
        self._stack.setCurrentIndex(self.SCREEN_SELECTOR)
