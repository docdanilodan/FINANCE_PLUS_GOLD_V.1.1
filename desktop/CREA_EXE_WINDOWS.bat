@echo off
setlocal
chcp 65001 >nul
title Crea EXE FINANCE_PLUS_UNICO
where py >nul 2>nul
if %errorlevel% equ 0 (set "PYCMD=py -3") else (set "PYCMD=python")
cd /d "%~dp0"
%PYCMD% -m venv .buildvenv
call .buildvenv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name FINANCE_PLUS_UNICO_DESKTOP FINANCE_PLUS_UNICO_DESKTOP.py
if exist dist\FINANCE_PLUS_UNICO_DESKTOP.exe (
  echo.
  echo EXE creato: %CD%\dist\FINANCE_PLUS_UNICO_DESKTOP.exe
  explorer dist
) else (
  echo Creazione EXE non riuscita.
)
pause
