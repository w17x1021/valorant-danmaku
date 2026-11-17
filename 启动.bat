@echo off
setlocal
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" -c "import PIL, tkinter" >nul 2>nul
if errorlevel 1 (
    echo 第一次运行，需要先安装依赖（约 10MB）...
    call "%~dp0install.bat"
    if errorlevel 1 goto fail
)

echo 正在启动 瓦罗兰特实时翻译弹幕 ...
"%PY%" -m app.main
if errorlevel 1 goto fail
exit /b 0

:fail
echo.
echo 启动失败，请把上面的报错内容截图发给作者。
pause
exit /b 1