@echo off
cd /d "%~dp0"

if not "%~1"=="" (
    "C:\ProgramData\miniconda3\pythonw.exe" "anylabeling\fast_send.py" "%~1"
    if not errorlevel 1 exit /b 0
)

call conda activate yolov26
python "anylabeling\app.py" --config "◊‘∂®“Â≈‰÷√1" %*