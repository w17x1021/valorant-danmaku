$root = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = Join-Path $desktop '瓦罗兰特翻译助手.lnk'

$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = Join-Path $root '.venv\Scripts\pythonw.exe'
$s.Arguments = '"' + (Join-Path $root 'run.pyw') + '"'
$s.WorkingDirectory = $root
$s.IconLocation = (Join-Path $root 'assets\app.ico') + ',0'
$s.Description = '瓦罗兰特实时翻译：队友文字/语音转中文弹幕，我说的话转日英可复制'
$s.WindowStyle = 1
$s.Save()

Write-Host "桌面快捷方式已创建：$lnk" -ForegroundColor Green
