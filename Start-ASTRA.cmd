@echo off
setlocal
cd /d "%~dp0"
if exist "dist\ASTRA-Desktop-2.4.1\ASTRA.exe" (
  "dist\ASTRA-Desktop-2.4.1\ASTRA.exe" %*
  exit /b
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 desktop_runtime.py --renderer "build\toolchain\godot\Godot_v4.7.2-stable_win64.exe" --project desktop --assets assets %*
) else (
  python desktop_runtime.py --renderer "build\toolchain\godot\Godot_v4.7.2-stable_win64.exe" --project desktop --assets assets %*
)
if errorlevel 1 pause
