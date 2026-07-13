@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] 创建 Python 虚拟环境...
  py -m venv .venv
  if errorlevel 1 goto :error
)

echo [2/3] 安装依赖...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [3/3] 开始下载北交所 F10...
".venv\Scripts\python.exe" bse_f10_downloader.py --output "%~dp0data" --start-year 2010
set code=%errorlevel%

echo.
echo 程序退出代码：%code%
echo 数据目录：%~dp0data
pause
exit /b %code%

:error
echo.
echo 安装或运行失败，请查看上面的错误信息。
pause
exit /b 1
