
@echo off
REM 激活 conda 环境
call conda activate xanylabeling

REM 切换到指定目录
cd /d "%~dp0"

REM 执行 Python 脚本
python anylabeling/app.py
