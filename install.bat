@echo off
title RoArm Mission Manager - Setup
color 0A
echo.
echo  =============================================
echo   RoArm Mission Manager
echo  =============================================
echo.

:: ── Check Python ──────────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found.
    echo.
    echo  Please install Python 3.9+ from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
    echo  [ERROR] Python 3.9+ required, found %PYVER%
    echo.
    echo  Please install Python 3.9+ from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo  [OK] %PYVER%

:: ── Install dependencies ──────────────────────────────────────────────────────
echo.
echo  Checking dependencies...
python -c "import serial" >nul 2>&1
if not errorlevel 1 (
    echo  [OK] pyserial already installed
    goto :launch
)
echo  Installing pyserial...
python -m pip install pyserial --quiet
if errorlevel 1 (
    echo.
    echo  [ERROR] Failed to install pyserial.
    echo  Try running this script as Administrator, or run manually:
    echo    pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo  [OK] pyserial installed

:: ── Launch ────────────────────────────────────────────────────────────────────
:launch
echo.
echo  Starting launcher...
echo.
python "%~dp0launcher.py"
