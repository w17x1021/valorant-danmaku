# 用 PyInstaller 打包绿色版：build\dist\ValorantDanmaku\ValorantDanmaku.exe
#
# 用法（在项目根目录）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_exe.ps1
#   powershell ... -File tools\build_exe.ps1 -Console      # 带黑框，方便看报错
#
# 说明：仓库里原来没有打包脚本，这个文件把「怎么打」固定下来，
# 免得下次又要靠回忆自己敲一堆 --collect-all。

param(
    [string]$Python = "",
    [string]$OutDir = "",
    [switch]$Console
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $Python) {
    $candidate = Join-Path $root ".venv\Scripts\python.exe"
    if (Test-Path $candidate) { $Python = $candidate } else { $Python = "python" }
}
if (-not $OutDir) { $OutDir = Join-Path $root "build" }

Write-Host "Python : $Python"
Write-Host "输出   : $OutDir"
& $Python -c "import PyInstaller, sys; print('PyInstaller', PyInstaller.__version__, '| Python', sys.version.split()[0])"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 没装：先运行 $Python -m pip install pyinstaller" }

$mode = if ($Console) { "--console" } else { "--windowed" }
$dist = Join-Path $OutDir "dist"
$work = Join-Path $OutDir "work"

# 这些包有大量数据文件 / 动态导入，PyInstaller 的默认 hook 抓不全
$collectAll = @(
    "paddlex", "paddle", "cv2",
    "ctranslate2", "faster_whisper", "tokenizers",
    "soundcard", "av", "onnxruntime",
    "huggingface_hub"
)

$cliArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    $mode,
    "--onedir",
    "--name", "ValorantDanmaku",
    "--distpath", $dist,
    "--workpath", $work,
    "--specpath", $OutDir,
    "--icon", (Join-Path $root "assets\app.ico"),
    "--add-data", "$root\assets;assets",
    "--add-data", "$root\app\ocr\ocr_worker.ps1;app\ocr",
    "--hidden-import", "paddlex",
    "--exclude-module", "pytest",
    "--exclude-module", "matplotlib",
    "--exclude-module", "IPython",
    "--exclude-module", "torch",
    (Join-Path $root "run.pyw")
)
foreach ($pkg in $collectAll) { $cliArgs += @("--collect-all", $pkg) }

Write-Host ""
Write-Host "开始打包（首次约 5~15 分钟）..." -ForegroundColor Cyan
& $Python @cliArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失败，退出码 $LASTEXITCODE" }

$exe = Join-Path $dist "ValorantDanmaku\ValorantDanmaku.exe"
if (-not (Test-Path $exe)) { throw "没找到 $exe" }

$size = [math]::Round((Get-ChildItem (Split-Path $exe) -Recurse -File |
                       Measure-Object -Sum Length).Sum / 1MB, 0)
Write-Host ""
Write-Host "打包完成：$exe" -ForegroundColor Green
Write-Host "整包大小：$size MB"
