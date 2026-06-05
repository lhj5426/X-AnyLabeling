 @echo off
if "%1" == "h" goto begin
mshta vbscript:createobject("wscript.shell").run("""%~nx0"" h",0)(window.close)&&exit
:begin
REM
@echo off
REM 激活 conda 环境
call conda activate yolov26

REM 切换到指定目录
cd /d "%~dp0"

REM 执行 Python 脚本
python anylabeling/app.py
