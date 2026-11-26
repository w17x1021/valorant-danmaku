@echo off
chcp 936 >nul
title 上传到 GitHub
cd /d "%~dp0"
set "REPO=https://github.com/w17x1021/valorant-danmaku.git"

echo ============================================
echo   上传 瓦罗兰特翻译助手 到 GitHub
echo   目标仓库: %REPO%
echo ============================================
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo [错误] 没找到 git，请先安装 Git for Windows
  pause & exit /b 1
)

rem 仓库还没建的话，先去网页创建（名字必须是英文）
git ls-remote "%REPO%" >nul 2>nul
if errorlevel 1 (
  echo [!] 访问不到这个仓库，通常是还没创建。
  echo     请在浏览器打开 https://github.com/new
  echo     仓库名填: valorant-danmaku
  echo     不要勾 README / gitignore / license，点 Create repository
  echo     建好后重新双击本脚本。
  pause & exit /b 1
)

git remote remove origin >nul 2>nul
git remote add origin "%REPO%"

echo 正在推送，可能会弹出 GitHub 登录窗口（浏览器里点 Authorize 即可）...
echo.
git push -u origin main
if errorlevel 1 (
  echo.
  echo [失败] 推送没成功，把上面的报错发给我。
  pause & exit /b 1
)

echo.
echo [+] 代码已推送。
echo.
echo 下一步（可选）：打一个版本标签，GitHub 会自动构建绿色版并放到 Releases
echo     继续按任意键就打标签 v1.0
pause >nul
git tag v1.0
git push origin v1.0
if errorlevel 1 (
  echo [提示] 标签推送失败（可能已经存在），不影响代码。
) else (
  echo [+] 标签已推送，几分钟后到仓库的 Releases 页面看构建结果。
)
echo.
pause
