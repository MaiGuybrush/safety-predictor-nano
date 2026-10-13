@echo off
set "SCRIPT_DIR=%~dp0"

"%SCRIPT_DIR%argus_predictor.exe" --report-issue %*
