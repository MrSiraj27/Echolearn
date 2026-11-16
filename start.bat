@echo off
rem EchoLearn: start the app after setup.bat has been run once.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\start.ps1"
timeout /t 8 >nul
