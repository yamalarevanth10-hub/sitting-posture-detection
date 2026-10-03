@echo off
title Digital Wellness Monitor - Desktop OpenCV
cd /d "%~dp0"
echo =====================================================================
echo   Digital Wellness Monitor - Desktop OpenCV Monitor
echo =====================================================================
echo.
echo Launching OpenCV camera window...
echo Keyboard Controls:
echo   [C] - Calibrate Upright Sitting Baseline
echo   [R] - Reset Session
echo   [Q] or [ESC] - Exit
echo.
python monitor_opencv.py
pause
