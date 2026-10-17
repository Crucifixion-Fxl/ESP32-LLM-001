@echo off
if "%~1"=="" (
  echo Usage: flash_nodes.bat COM_PORT
  exit /b 1
)
rem Run from an ESP-IDF command prompt. Model data must be flashed separately.
idf.py -C "%~dp0..\firmware\node" -p "%~1" flash
