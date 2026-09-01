@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo Programma non installato. Avvia prima INSTALLA_E_AVVIA_WINDOWS.bat
  pause
  exit /b 1
)
start "FINANCEPLUS" .venv\Scripts\pythonw.exe FINANCEPLUS_DESKTOP_V1_0.py
