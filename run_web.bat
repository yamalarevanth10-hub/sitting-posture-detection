@echo off
title Digital Wellness Monitor - Web Application
cd /d "%~dp0"
echo =====================================================================
echo   Digital Wellness Monitor - Posture & Eye Blink AI
echo   Major Project Web Application
echo =====================================================================
echo.
echo Starting FastAPI server at http://localhost:8000 ...
start "" "http://localhost:8000"
python app.py
pause
