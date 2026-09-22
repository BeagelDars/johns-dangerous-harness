@echo off
title Johns Dangerous Harness
cd /d "%~dp0"
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Harness exited with code %ERRORLEVEL%]
    pause
)
