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
echo   显卡加速（NVIDIA CUDA，可选）
echo   装了之后语音识别快约 2 倍
echo ============================================
echo.
echo 正在下载 cuBLAS + cuDNN（约 800MB，走清华镜像）...
"%PY%" -m pip install -q --upgrade nvidia-cublas-cu12 nvidia-cudnn-cu12 -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 goto fail

echo.
echo 验证 GPU 是否可用 ...
"%PY%" -c "import sys,sysconfig,os; from pathlib import Path; sp=Path(sysconfig.get_paths()['purelib']); [os.add_dll_directory(str(sp/p)) for p in ('nvidia/cublas/bin','nvidia/cudnn/bin','nvidia/cuda_nvrtc/bin') if (sp/p).exists()]; from faster_whisper import WhisperModel; m=WhisperModel('small', device='cuda', compute_type='float16', download_root='models', local_files_only=True); print('  GPU 可用')"
if errorlevel 1 goto fail

echo.
echo 装好了。重新启动程序，面板上会显示「语音 识别中·GPU」。
pause
exit /b 0

:fail
echo.
echo 安装失败（没有 N 卡/驱动太旧的话可以忽略，程序会自动用 CPU）。
pause
exit /b 1