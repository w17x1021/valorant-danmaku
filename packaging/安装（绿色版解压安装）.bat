@echo off
chcp 936 >nul
setlocal enabledelayedexpansion
title 安装 瓦罗兰特翻译助手
cd /d "%~dp0"

set "ZIP=%~dp0瓦罗兰特翻译助手-绿色版.zip"
if not exist "%ZIP%" (
  echo 找不到绿色版压缩包：%ZIP%
  echo 请把本 bat 和 zip 放在同一个文件夹里。
  pause & exit /b 1
)

set "TARGET=%~1"
if "%TARGET%"=="" (
  echo 请选择安装位置...
  for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms | Out-Null; $d=New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description='选择安装位置'; $d.SelectedPath='D:\'; if($d.ShowDialog() -eq 'OK'){ Write-Output $d.SelectedPath }"`) do set "TARGET=%%P"
)
if "%TARGET%"=="" (
  echo 已取消。
  pause & exit /b 1
)

set "DEST=%TARGET%\ValorantDanmaku"
echo 正在安装到：%DEST%
echo （大约 683 MB，请稍候…）
if not exist "%DEST%" mkdir "%DEST%"
powershell -NoProfile -Command "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%DEST%' -Force"
if not exist "%DEST%\ValorantDanmaku.exe" (
  echo 解压失败，请检查磁盘空间或被安全软件拦截。
  pause & exit /b 1
)

echo 正在创建桌面快捷方式...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\瓦罗兰特翻译助手.lnk'); $s.TargetPath='%DEST%\ValorantDanmaku.exe'; $s.WorkingDirectory='%DEST%'; $s.Save()"

echo.
echo 安装完成：%DEST%
echo 桌面已生成「瓦罗兰特翻译助手」快捷方式。
start "" "%DEST%\ValorantDanmaku.exe"
timeout /t 3 >nul
