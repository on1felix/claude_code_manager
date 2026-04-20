@echo off
echo ========================================
echo  Claude Code Manager - Build Script
echo ========================================
echo.

echo [1/3] Cleaning old build files...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del /q "*.spec"
echo Done!
echo.

echo [2/3] Building executable with PyInstaller...
cd /d "%~dp0"
pyinstaller --onefile --windowed --icon=icon.ico --name=ClaudeCodeManager --add-data "icon.ico;." --add-data "icon.png;." --add-data "icon-download-blue.svg;." claude_code_manager.pyw --clean
echo.

if exist "dist\ClaudeCodeManager.exe" (
    echo [3/3] Build successful!
    echo.
    echo ========================================
    echo  ClaudeCodeManager.exe created!
    echo  Location: dist\ClaudeCodeManager.exe
    echo ========================================
    echo.
    echo Opening dist folder...
    explorer dist
) else (
    echo [3/3] Build FAILED!
    echo.
    echo ========================================
    echo  Error: ClaudeCodeManager.exe not found
    echo ========================================
)

echo.
pause
