@echo off
"%~dp0venv\Scripts\python.exe" "%~dp0view_detections.py" %*
if errorlevel 1 pause
