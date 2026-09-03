@echo off
setlocal
chcp 65001 >nul
title Crea EXE FINANCE_PLUS_UNICO DESKTOP V1.1
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  call INSTALLA_E_AVVIA_WINDOWS.bat
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name FINANCE_PLUS_UNICO_DESKTOP_V1_1 FINANCE_PLUS_UNICO_DESKTOP.py
if exist dist\FINANCE_PLUS_UNICO_DESKTOP_V1_1.exe (
  echo.
  echo EXE creato: %CD%\dist\FINANCE_PLUS_UNICO_DESKTOP_V1_1.exe
  explorer dist
) else (
  echo Creazione EXE non riuscita.
)
pause
