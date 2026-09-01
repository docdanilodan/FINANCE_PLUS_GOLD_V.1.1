@echo off
chcp 65001 >nul
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0FINANCE_PLUS_UNICO_DESKTOP.py"
) else (
  python "%~dp0FINANCE_PLUS_UNICO_DESKTOP.py"
)
