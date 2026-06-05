@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

REM ȡǰļ
for %%* in (.) do set "folder=%%~nx*"

REM ȡ
for /f "tokens=3 delims=-" %%a in ("%folder%") do set "date=%%a"
set "date=!date:mogai=mogai_!"

REM ļ·
set "file=anylabeling\app_info.py"
set "tempfile=anylabeling\app_info_temp.py"

REM ʱļ
> "%tempfile%" (
    for /f "usebackq tokens=* delims=" %%l in ("%file%") do (
        set "line=%%l"

        echo !line! | findstr /b /c:"__appname__ =" >nul
        if !errorlevel! == 0 (
            echo __appname__ = "!date!_X-AnyLabeling"
        ) else (
            echo !line! | findstr /b /c:"__preferred_device__ =" >nul
            if !errorlevel! == 0 (
                echo __preferred_device__ = "GPU"  # GPU or CPU
            ) else (
                echo !line!
            )
        )
    )
)

REM 滻ԭļ
move /y "%tempfile%" "%file%" >nul

echo 成功修改 __appname__ 和 __preferred_device__
set /p dummy=请按任意键继续. . . 