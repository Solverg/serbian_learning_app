@echo off
pyinstaller --onefile --windowed --name "SerbianFlashcards" --add-data "data;data" --add-data "assets;assets" main.py
echo.
echo Build complete. Executable: dist\SerbianFlashcards.exe
pause
