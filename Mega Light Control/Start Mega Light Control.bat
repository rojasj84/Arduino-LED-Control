@echo off
setlocal
cd /d "%~dp0"
python -c "import sys" >nul 2>nul
if errorlevel 1 (
    py -3 -c "import pathlib, subprocess, sys, tkinter, serial; subprocess.Popen([str(pathlib.Path(sys.executable).with_name('pythonw.exe')), 'mega_light_control.py'] + sys.argv[1:])" %*
) else (
    python -c "import pathlib, subprocess, sys, tkinter, serial; subprocess.Popen([str(pathlib.Path(sys.executable).with_name('pythonw.exe')), 'mega_light_control.py'] + sys.argv[1:])" %*
)
if errorlevel 1 (
    echo.
    echo Install Python 3 and pyserial: python -m pip install -r requirements.txt
    pause
)
