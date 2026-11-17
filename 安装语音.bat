@echo off
setlocal
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo 请先双击 启动.bat 或 install.bat 完成基础安装
    pause
    exit /b 1
)

echo ============================================
echo   语音识别组件安装（约 120MB + 460MB 模型）
echo ============================================
echo.
echo [1/2] 安装 Python 依赖 ...
"%PY%" -m pip install -q -r requirements-voice.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 goto fail

echo [2/2] 下载语音识别模型 small（约 460MB，走 hf-mirror 镜像，请耐心等待）...
set HF_ENDPOINT=https://hf-mirror.com
set HF_HUB_DISABLE_XET=1
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
"%PY%" -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8', download_root='models'); print('  模型就绪')"
if errorlevel 1 goto fail

echo.
echo 语音组件安装完成，重新启动 启动.bat 即可。
pause
exit /b 0

:fail
echo.
echo 安装失败，请把上面的报错截图发给我。
pause
exit /b 1