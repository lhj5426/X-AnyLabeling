@echo off
REM Activate conda environment
call conda activate yolov26

REM Switch to the project directory containing this BAT
cd /d "%~dp0"

REM Launch with the Chinese configuration group
python anylabeling/app.py --config "±äÉ«±êÇ©"


