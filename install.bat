@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   瓦罗兰特实时翻译弹幕 - 环境安装
echo ============================================
echo.

set "PYCMD="
where py >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD where python >nul 2>nul && set "PYCMD=python"
if not defined PYCMD (
    echo [错误] 没有找到 Python，请先安装 Python 3.10 以上版本：
    echo        https://www.python.org/downloads/
    echo        安装时记得勾选 "Add Python to PATH"
    pause
    exit /b 1
)

echo [1/3] 创建虚拟环境 .venv ...
if not exist ".venv\Scripts\python.exe" (
    %PYCMD% -m venv .venv || goto fail
)

echo [2/3] 安装依赖（清华镜像）...
".venv\Scripts\python.exe" -m pip install -q --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple || goto fail

echo [3/3] 自检 ...
".venv\Scripts\python.exe" -c "import tkinter, PIL; print('  tkinter', tkinter.TkVersion, '| Pillow', PIL.__version__)" || goto fail

echo.
echo 安装完成，现在可以双击 启动.bat 了。
pause
exit /b 0

:fail
echo.
echo 安装失败，请把上面的报错截图发给作者。
pause
exit /b 1