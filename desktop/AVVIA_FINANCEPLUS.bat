@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo Programma non installato. Avvia prima INSTALLA_WINDOWS.bat
  pause
  exit /b 1
)
start "FINANCE_PLUS_UNICO" .venv\Scripts\pythonw.exe FINANCE_PLUS_UNICO_DESKTOP.py
