@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Create it first with: python -m venv .venv
    exit /b 1
)

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean DueClacSystem.spec
if errorlevel 1 (
    echo.
    echo Build failed.
    exit /b 1
)

echo.
echo Build completed.
echo EXE path: %ROOT_DIR%dist\DueClacSystem.exe
endlocal
