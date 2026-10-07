@echo off
:: ==============================================================================
:: run.bat - Argus Safety Predictor Nano Windows Runner
:: ==============================================================================
:: 1. Force CWD to repository root and inject ARGUS_MANAGED_RUNNER=1
:: 2. Provide outer supervisor loop listening to Exit Code 42
:: ==============================================================================

chcp 65001 >nul
setlocal enabledelayedexpansion

:: 1. Lock working directory to script directory
cd /d "%~dp0"
echo [run.bat] Working directory locked to: %CD%

:: 2. Inject managed runner flag and environment variables
set "ARGUS_MANAGED_RUNNER=1"
set "PYTHONUNBUFFERED=1"
set "OPENCV_LOG_LEVEL=ERROR"
set "OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp"
if defined PYTHONPATH (
    set "PYTHONPATH=src;!PYTHONPATH!"
) else (
    set "PYTHONPATH=src"
)

:: 3. Detect Python command
set "PYTHON_CMD="
if exist ".\venv\Scripts\python.exe" (
    set "PYTHON_CMD=.\venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=python"
)

:: 4. Detect target executable
set "TARGET_CMD="
if exist ".\argus_predictor\argus_predictor.exe" (
    set "TARGET_CMD=.\argus_predictor\argus_predictor.exe"
) else if exist ".\argus_predictor.exe" (
    set "TARGET_CMD=.\argus_predictor.exe"
) else if exist ".\main.py" (
    set "TARGET_CMD=!PYTHON_CMD! main.py"
) else (
    echo [run.bat] Error: Cannot find argus_predictor.exe or main.py
    exit /b 1
)

:: 5. Detect install.py script
set "INSTALL_SCRIPT="
if exist ".\scripts\install.py" (
    set "INSTALL_SCRIPT=.\scripts\install.py"
) else if exist ".\install.py" (
    set "INSTALL_SCRIPT=.\install.py"
)

:: 6. Supervisor loop
:loop
echo [run.bat] Launching Argus Safety Predictor Nano: !TARGET_CMD! %*

!TARGET_CMD! %*
set "EXIT_CODE=!ERRORLEVEL!"

echo [run.bat] Process exited with code: !EXIT_CODE!

if "!EXIT_CODE!"=="42" goto handle_42
if "!EXIT_CODE!"=="0" goto handle_0
goto handle_crash

:handle_42
echo [run.bat] Received Exit Code 42 (RESTART_FOR_UPDATE). Applying updates...
if exist "updates\staging\manifest.json" (
    echo [run.bat] Detected delta update in updates\staging. Running install.py --delta updates\staging...
    if defined INSTALL_SCRIPT (
        !PYTHON_CMD! "!INSTALL_SCRIPT!" --delta updates\staging
        if !ERRORLEVEL! neq 0 (
            echo [run.bat] Error: install.py --delta failed. Rolling back...
            !PYTHON_CMD! "!INSTALL_SCRIPT!" --rollback
        )
    ) else (
        echo [run.bat] Warning: install.py not found. Skipping swap.
    )
)
timeout /t 1 /nobreak >nul
goto loop

:handle_0
echo [run.bat] Normal termination (Exit 0). Exiting runner.
exit /b 0

:handle_crash
if not exist .update_in_progress goto abort_crash

echo [run.bat] Warning: Abnormal exit during update (Code: !EXIT_CODE!). Triggering rollback...
if defined INSTALL_SCRIPT (
    !PYTHON_CMD! "!INSTALL_SCRIPT!" --rollback
) else if exist argus_predictor_bak (
    if exist argus_predictor move argus_predictor argus_predictor_failed >nul 2>nul
    move argus_predictor_bak argus_predictor >nul 2>nul
    echo Update failed (Code: !EXIT_CODE!), rolled back to previous version > .rollback_alert
)
if exist .update_in_progress del /f /q .update_in_progress >nul 2>nul
echo [run.bat] Rollback completed. Relaunching previous version...
timeout /t 2 /nobreak >nul
goto loop

:abort_crash
echo [run.bat] Application exited abnormally with code: !EXIT_CODE!
exit /b !EXIT_CODE!
