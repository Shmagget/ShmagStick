@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
set "SHMAGSTICK_HOME=%ROOT%"

set "PYTHON="
if exist "%ROOT%.venv\Scripts\pythonw.exe" set "PYTHON=%ROOT%.venv\Scripts\pythonw.exe"
if not defined PYTHON where py >nul 2>&1 && set "PYTHON=pyw -3"
if not defined PYTHON where pythonw >nul 2>&1 && set "PYTHON=pythonw"

if not defined PYTHON goto :missing
%PYTHON% -c "import PyQt6, psutil" >nul 2>&1
if errorlevel 1 goto :missingdeps

start "" %PYTHON% "%ROOT%shmagstick.py"
exit /b 0

:missing
echo ShmagStick needs Python 3.9 or newer with PyQt6 and psutil.
echo Install Python, then run: python -m pip install -r requirements.txt
pause
exit /b 1

:missingdeps
echo Python was found, but PyQt6 or psutil is missing.
echo Run: python -m pip install -r requirements.txt
pause
exit /b 1
