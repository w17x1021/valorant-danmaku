@echo off
chcp 936 >nul
title 关闭卡住的后台实例
echo 正在以管理员身份清理残留进程...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-Command','Get-CimInstance Win32_Process -Filter \"Name=''pythonw.exe'' OR Name=''python.exe''\" | Where-Object { $_.ExecutablePath -like \"*valorant-danmaku*\" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; \"killed \" + $_.ProcessId }'"
echo.
echo 如果弹出 UAC 请点「是」，然后等 2 秒。
timeout /t 5 >nul