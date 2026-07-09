@echo off
setlocal
title PPTY SCOPE - PYSLY-R90 - Paisley Ponytail - WAYBACK RADAR
cd /d "%~dp0"
color 0A

echo.
echo   PPTY  -  PYSLY-R90  -  SECTOR ARCHIVE
echo   Paisley Ponytail - the Webshots Resurrector
echo   Opening scope glass...
echo.

rem Find a Python launcher
set "PY="
py --version >nul 2>nul
if not errorlevel 1 set "PY=py"
if not defined PY (
    python --version >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY goto nopython

if exist ".venv\Scripts\python.exe" goto havevenv

echo   First run: building private workspace .venv ...
%PY% -m venv .venv
if not exist ".venv\Scripts\python.exe" goto novenv

:havevenv
set "VPY=.venv\Scripts\python.exe"

echo   Checking dependencies...
"%VPY%" -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 goto pipfail

echo   Launching scope...
"%VPY%" resurrector.py scope
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
    echo.
    echo   Scope exited with error code %ERR%.
    echo.
    pause
)
goto end

:novenv
echo   Could not build .venv - trying system Python...
%PY% -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 goto pipfail
%PY% resurrector.py scope
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
    echo.
    echo   Scope exited with error code %ERR%.
    echo.
    pause
)
goto end

:nopython
echo.
echo   Python is not installed yet. Free:
echo     1. https://www.python.org/downloads/
echo     2. Tick "Add python.exe to PATH"
echo     3. Double-click Start_Here.bat again
echo.
pause
goto end

:pipfail
echo.
echo   Could not install requirements. Check internet, try again.
echo.
pause
goto end

:end
endlocal
