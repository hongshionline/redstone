@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo.
  echo [首次运行] 正在准备红石联机运行环境...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.12 -m venv ".venv" >nul 2>nul
    if not exist "%PY%" py -3 -m venv ".venv"
  ) else (
    where python >nul 2>nul
    if errorlevel 1 (
      echo 未检测到 Python。
      echo 请双击“新电脑安装引导.cmd”安装 Python 后，再运行本文件。
      pause
      exit /b 1
    )
    python -m venv ".venv"
  )
)

if not exist "%PY%" (
  echo 创建运行环境失败。
  pause
  exit /b 1
)

"%PY%" -c "import PySide6" >nul 2>nul
if errorlevel 1 (
  echo 正在安装运行依赖，请保持网络正常...
  "%PY%" -m pip install --disable-pip-version-check --upgrade pip
  if errorlevel 1 goto :deps_failed
  "%PY%" -m pip install --disable-pip-version-check --prefer-binary -r requirements.txt
  if errorlevel 1 goto :deps_failed
)

if exist ".venv\Scripts\pythonw.exe" (
  start "" /b ".venv\Scripts\pythonw.exe" "%~dp0main.py"
) else (
  "%PY%" "%~dp0main.py"
)
exit /b 0

:deps_failed
echo.
echo 依赖安装失败，请检查网络后重新运行。
pause
exit /b 1
