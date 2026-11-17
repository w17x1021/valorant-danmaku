# 安装「日本語 OCR 语言包」，让程序能识别队友打的日文
$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $pr = New-Object Security.Principal.WindowsPrincipal($id)
    return $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "需要管理员权限来安装语言功能，正在弹出 UAC 授权框，请点「是」..." -ForegroundColor Yellow
    $args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"")
    Start-Process powershell.exe -Verb RunAs -ArgumentList $args
    exit 0
}

Write-Host "正在查询可安装的语言包..." -ForegroundColor Cyan
$caps = @(Get-WindowsCapability -Online | Where-Object { $_.Name -like "Language.OCR*ja-JP*" })
if ($caps.Count -eq 0) {
    Write-Host "没有找到日语 OCR 组件，请改用：设置 → 时间和语言 → 语言和区域 → 添加语言 → 日本語 → 安装语言功能" -ForegroundColor Red
    Read-Host "按回车关闭"
    exit 1
}

foreach ($cap in $caps) {
    if ($cap.State -ne "Installed") {
        Write-Host "正在安装 $($cap.Name)（约 30~60MB，取决于网速）..." -ForegroundColor Cyan
        try {
            Add-WindowsCapability -Online -Name $cap.Name | Out-Null
        } catch {
            Write-Host "安装失败：$($_.Exception.Message)" -ForegroundColor Red
        }
        # 等它真的落地；如果一直停在 InstallPending，多半是下载服务器连不上
        for ($i = 0; $i -lt 24; $i++) {
            $st = (Get-WindowsCapability -Online -Name $cap.Name).State
            if ($st -eq "Installed") { break }
            Start-Sleep -Seconds 5
        }
        $st = (Get-WindowsCapability -Online -Name $cap.Name).State
        if ($st -ne "Installed") {
            Write-Host ""
            Write-Host "安装卡在 [$st]，组件下载不下来。" -ForegroundColor Yellow
            Write-Host "常见的两个原因：" -ForegroundColor Yellow
            Write-Host "  1) 微软的补丁服务器在这个网络下不通（国内很常见）→ 挂代理/VPN 后再运行一次本脚本" -ForegroundColor Yellow
            Write-Host "  2) Windows Update 服务被禁用 → 设置里打开「Windows 更新」后再试" -ForegroundColor Yellow
            Write-Host "装完或者重启后，再运行本脚本会显示『已经安装过了』。" -ForegroundColor Yellow
        }
    } else {
        Write-Host "$($cap.Name) 已经安装过了" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "当前系统可用的 OCR 语言：" -ForegroundColor Cyan
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$langs = @([Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages | ForEach-Object { $_.LanguageTag })
$langs | ForEach-Object { Write-Host "  - $_" }

if ($langs -contains "ja" -or ($langs | Where-Object { $_ -like "ja*" })) {
    Write-Host ""
    Write-Host "日语识别已就绪 ✓  请重新启动「启动.bat」" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "日语仍不可用。可以手动装：设置 → 时间和语言 → 语言和区域 → 添加语言 → 日本語 → 语言功能里勾选「光学字符识别」" -ForegroundColor Yellow
}
Read-Host "按回车关闭"
