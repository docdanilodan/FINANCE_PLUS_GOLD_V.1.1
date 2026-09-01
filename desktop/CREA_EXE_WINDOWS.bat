@echo off
setlocal
chcp 65001 >nul
title Crea EXE FINANCEPLUS DESKTOP V1.0
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  call INSTALLA_E_AVVIA_WINDOWS.bat
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name FINANCEPLUS_DESKTOP_V1_0 FINANCEPLUS_DESKTOP_V1_0.py
if exist dist\FINANCEPLUS_DESKTOP_V1_0.exe (
  echo.
  echo EXE creato: %CD%\dist\FINANCEPLUS_DESKTOP_V1_0.exe
  explorer dist
) else (
  echo Creazione EXE non riuscita.
)
pause
