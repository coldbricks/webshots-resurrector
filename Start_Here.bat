@echo off
title Paisley Ponytail - the Webshots Resurrector
cd /d "%~dp0"

rem Find a Python launcher
set PY=
py --version >nul 2>nul
if not errorlevel 1 set PY=py
if not defined PY (
    python --version >nul 2>nul
    if not errorlevel 1 set PY=python
)
if not defined PY goto nopython

rem The tool keeps its parts in a private workspace here in its own
rem folder - a Python "venv" - so it never touches anything else
rem installed on this machine. Delete the .venv folder to reset it.
if not exist ".venv\Scripts\python.exe" (
    echo First run: building the tool a private workspace. One-time, about a minute...
    %PY% -m venv .venv
)
if not exist ".venv\Scripts\python.exe" goto novenv
set VPY=.venv\Scripts\python.exe

"%VPY%" -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 goto pipfail
"%VPY%" resurrector.py
goto end

:novenv
rem Couldn't build the venv. Unusual - but don't strand the user over
rem plumbing. Fall back to the system Python, the pre-v1.6.2 behavior.
echo Couldn't build the private workspace. Using the system Python instead.
%PY% -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 goto pipfail
%PY% resurrector.py
goto end

:nopython
echo.
echo  Python isn't installed yet. It's free:
echo.
echo    1. Go to  https://www.python.org/downloads/
echo    2. Download and run the installer
echo    3. IMPORTANT: tick the "Add python.exe to PATH" box
echo    4. Double-click Start_Here.bat again
echo.
goto end

:pipfail
echo.
echo  Couldn't install the requirements. Check your internet connection
echo  and run Start_Here.bat again.
echo.

:end
pause
