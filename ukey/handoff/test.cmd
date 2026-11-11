@echo off
setlocal
where py.exe >nul 2>&1
if not errorlevel 1 goto launcher
where python.exe >nul 2>&1
if errorlevel 1 goto missing
python "%~dp0test.py" %*
exit /b %errorlevel%
:launcher
py -3 "%~dp0test.py" %*
exit /b %errorlevel%
:missing
echo Python 3.10 or later is required.
exit /b 2
