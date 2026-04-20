@echo off
title RoArm Mission Manager - Setup
color 0A
echo.
echo  =============================================
echo   RoArm Mission Manager - First-time Setup
echo  =============================================
echo.

:: ── Check Python ──────────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found.
    echo.
    echo  Please install Python from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo  [OK] Found %PYVER%
echo.

:: ── Install pyserial (skip if already installed) ────────────────────────────
echo  Checking pyserial...
python -c "import serial" >nul 2>&1
if not errorlevel 1 (
    echo  [OK] pyserial already installed
    echo.
    goto :detect
)
echo  Installing pyserial...
python -m pip install pyserial --quiet
if errorlevel 1 (
    echo.
    echo  [ERROR] Failed to install pyserial.
    echo  Try running this script as Administrator, or install manually:
    echo    pip install -r requirements.txt
    pause
    exit /b 1
)
echo  [OK] pyserial installed
echo.

:detect

:: ── Detect arm by USB VID:PID ─────────────────────────────────────────────────
echo  Looking for RoArm (ESP32 USB-serial adapter)...
echo.

:: Write detection script to a temp file (avoids broken multiline -c syntax)
(
    echo import serial.tools.list_ports
    echo KNOWN = [('10C4','EA60','CP210x'),('1A86','7523','CH340'),('1A86','55D4','CH9102'),('0403','6001','FTDI'),('303A','1001','ESP32-USB')]
    echo ports = list(serial.tools.list_ports.comports())
    echo matches = [(p.device, n, '%s:%s' %% (format(p.vid,'04X'), format(p.pid,'04X'))) for p in ports for v,pi,n in KNOWN if p.vid and p.pid and format(p.vid,'04X')==v and format(p.pid,'04X')==pi]
    echo if matches:
    echo     for d,n,vp in matches: print('MATCH|' + d + '|' + n + '|' + vp)
    echo elif ports:
    echo     for p in ports:
    echo         vid = format(p.vid,'04X') if p.vid else '????'
    echo         pid = format(p.pid,'04X') if p.pid else '????'
    echo         print('PORT|' + p.device + '|' + p.description + '|' + vid + ':' + pid)
    echo else:
    echo     print('NONE')
) > "%TEMP%\roarm_detect.py"

python "%TEMP%\roarm_detect.py" > "%TEMP%\roarm_detect.txt" 2>nul
del "%TEMP%\roarm_detect.py" >nul 2>&1

:: Read results
set AUTO_PORT=
set AUTO_VIDPID=
set MATCH_COUNT=0
for /f "tokens=1,2,3,4 delims=|" %%A in (%TEMP%\roarm_detect.txt) do (
    if "%%A"=="MATCH" (
        set /a MATCH_COUNT+=1
        if not defined AUTO_PORT (
            set AUTO_PORT=%%B
            set AUTO_VIDPID=%%D
        )
        echo    %%B  -  %%C  [%%D]
    )
    if "%%A"=="PORT" echo    %%B  -  %%C  [%%D]
    if "%%A"=="NONE" echo    (no serial ports found - is the arm plugged in?)
)

if defined AUTO_PORT (
    echo.
    echo  [OK] Found arm on %AUTO_PORT% - will auto-detect by USB ID each launch.
    set COMPORT=%AUTO_PORT%
) else (
    echo.
    echo  Could not identify the arm automatically.
    set /p COMPORT= Enter COM port manually (e.g. COM3):
    set AUTO_VIDPID=
)
del "%TEMP%\roarm_detect.txt" >nul 2>&1

:: ── Write launch.bat ──────────────────────────────────────────────────────────
echo.
echo  Writing launch.bat...
(
    echo @echo off
    echo title RoArm Mission Manager
    echo color 0A
    echo echo.
    echo echo  RoArm Mission Manager
    echo echo.
) > "%~dp0launch.bat"

if defined AUTO_VIDPID (
    (
        echo set VIDPID=%AUTO_VIDPID%
        echo echo  Locating arm by USB ID ^(%AUTO_VIDPID%^)...
        echo python -c "import serial.tools.list_ports,sys; vid,pid=[int(x,16) for x in '%AUTO_VIDPID%'.split(':')]; r=[p.device for p in serial.tools.list_ports.comports() if p.vid==vid and p.pid==pid]; print(r[0] if r else '')" ^> %%TEMP%%\roarm_port.txt
        echo set /p COMPORT=^<%%TEMP%%\roarm_port.txt
        echo del %%TEMP%%\roarm_port.txt ^>nul 2^>^&1
        echo if "%%COMPORT%%"=="" ^(
        echo     echo  [ERROR] Arm not found. Check USB cable.
        echo     pause
        echo     exit /b 1
        echo ^)
        echo echo  [OK] Found arm on %%COMPORT%%
    ) >> "%~dp0launch.bat"
) else (
    (
        echo set COMPORT=%COMPORT%
        echo echo  Using port: %COMPORT%
    ) >> "%~dp0launch.bat"
)

(
    echo echo.
    echo echo  Open browser at: http://localhost:5000
    echo echo  Press Ctrl+C here to stop.
    echo echo.
    echo start "" http://localhost:5000
    echo python "%~dp0server.py" --port %%COMPORT%%
    echo pause
) >> "%~dp0launch.bat"

echo.
echo  =============================================
echo   Setup complete!
echo  =============================================
echo.
echo  Double-click launch.bat to start the Mission Manager.
if defined AUTO_VIDPID (
    echo  The arm will be found automatically even if the COM port changes.
)
echo.
pause
