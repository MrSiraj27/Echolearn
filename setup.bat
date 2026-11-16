@echo off
rem EchoLearn: one-time setup (installs everything, creates the database, starts the app).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\setup.ps1" %*
echo.
pause
