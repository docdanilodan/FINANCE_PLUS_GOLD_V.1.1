@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Installazione FINANCE_PLUS_UNICO DESKTOP
color 1F
echo ================================================================
echo   FINANCE_PLUS_UNICO DESKTOP V1.1 - INSTALLAZIONE WINDOWS
echo ================================================================
echo.
where py >nul 2>nul
if %errorlevel% neq 0 (
  where python >nul 2>nul
  if %errorlevel% neq 0 (
    echo Python non trovato. Provo a installare Python 3.12 con winget...
    where winget >nul 2>nul
    if %errorlevel% neq 0 (
      echo ERRORE: Python e winget non sono disponibili.
      echo Installa Python 3.12 da python.org selezionando "Add Python to PATH".
      pause
      exit /b 1
    )
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  )
)
set "APPDIR=%LOCALAPPDATA%\FinancePlusUnicoApp"
if not exist "%APPDIR%" mkdir "%APPDIR%"
copy /Y "%~dp0FINANCE_PLUS_UNICO_DESKTOP.py" "%APPDIR%\FINANCE_PLUS_UNICO_DESKTOP.py" >nul
copy /Y "%~dp0requirements.txt" "%APPDIR%\requirements.txt" >nul
cd /d "%APPDIR%"
where py >nul 2>nul
if %errorlevel% equ 0 (set "PYCMD=py -3") else (set "PYCMD=python")
echo Creo ambiente Python dedicato...
%PYCMD% -m venv .venv
if %errorlevel% neq 0 goto :fail
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 goto :fail
(
 echo @echo off
 echo cd /d "%%LOCALAPPDATA%%\FinancePlusUnicoApp"
 echo start "" .venv\Scripts\pythonw.exe FINANCE_PLUS_UNICO_DESKTOP.py
) > "%APPDIR%\AVVIA_FINANCE_PLUS.bat"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\FINANCE_PLUS_UNICO.lnk'); $s.TargetPath='%APPDIR%\AVVIA_FINANCE_PLUS.bat'; $s.WorkingDirectory='%APPDIR%'; $s.IconLocation='%SystemRoot%\System32\shell32.dll,21'; $s.Save()"
echo.
echo ================================================================
echo INSTALLAZIONE COMPLETATA.
echo Sul Desktop trovi: FINANCE_PLUS_UNICO
echo Dati locali: %LOCALAPPDATA%\FinancePlusUnico
echo ================================================================
start "" "%APPDIR%\AVVIA_FINANCE_PLUS.bat"
pause
exit /b 0
:fail
echo.
echo Installazione non completata. Controlla la connessione Internet e riprova.
pause
exit /b 1
