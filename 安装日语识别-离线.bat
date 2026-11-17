@echo off
setlocal
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo 请先双击 启动.bat 完成基础安装
    pause
    exit /b 1
)

echo ============================================
echo   日文文字识别 - 离线引擎（PaddleOCR）
echo   适用：Windows 日语语言包装不上时
echo ============================================
echo.
echo [1/2] 安装识别引擎（约 250MB，走清华镜像）...
"%PY%" -m pip install -q -r requirements-ja.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 goto fail

echo [2/2] 预热模型（约 10MB，从百度云 CDN 下载）...
set PADDLE_PDX_CACHE_HOME=%~dp0cache\paddlex
"%PY%" -c "import os; os.environ.setdefault('PADDLE_PDX_CACHE_HOME', r'%~dp0cache\paddlex'); from paddlex import create_model; m=create_model('PP-OCRv5_mobile_rec'); print('  模型就绪')"
if errorlevel 1 goto fail

echo.
echo 装好了。重新启动 启动.bat，程序会自动用它识别日文。
pause
exit /b 0

:fail
echo.
echo 安装失败，请把上面的报错截图发给我。
pause
exit /b 1