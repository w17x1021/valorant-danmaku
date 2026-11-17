$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root '.venv\Scripts\pythonw.exe'
$script = Join-Path $root 'run.pyw'
if (-not (Test-Path $py)) {
    Write-Host '还没有安装依赖，请先运行 启动.bat' -ForegroundColor Red
    Read-Host '按回车关闭'
    exit 1
}
try {
    Start-Process -FilePath $py -ArgumentList ('"' + $script + '"') -WorkingDirectory $root -Verb RunAs
    Write-Host '已用管理员身份启动。' -ForegroundColor Green
} catch {
    Write-Host ('启动失败：' + $_.Exception.Message) -ForegroundColor Red
    Read-Host '按回车关闭'
}
