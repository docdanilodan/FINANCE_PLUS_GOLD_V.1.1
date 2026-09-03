@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo   FINANCE_PLUS_UNICO DESKTOP V1.1 - INSTALLAZIONE
echo ===============================================
where python >nul 2>nul
if errorlevel 1 (
  echo Python non trovato. Provo a installarlo con winget...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo ERRORE: installa Python 3.11 o superiore da python.org e rilancia questo file.
    pause
    exit /b 1
  )
  winget install -e --id Python.Python.3.12
)
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo ERRORE durante l'installazione delle librerie.
  pause
  exit /b 1
)
set LAUNCH=%~dp0AVVIA_FINANCEPLUS.bat
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\FINANCEPLUS DESKTOP.lnk'); $s.TargetPath='%~dp0AVVIA_FINANCEPLUS.bat'; $s.WorkingDirectory='%~dp0'; $s.Save()" >nul 2>nul
echo Installazione completata. Avvio FINANCEPLUS...
start "" "%~dp0AVVIA_FINANCEPLUS.bat"
exit /b 0
