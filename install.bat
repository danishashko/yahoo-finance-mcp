@echo off
REM Yahoo Finance MCP Server - Easy Installation Script for Windows
REM This script will install all necessary dependencies

echo ======================================
echo Yahoo Finance MCP Server Installation
echo ======================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed!
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python found
python --version
echo.

REM Check if pip is installed
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pip is not installed!
    pause
    exit /b 1
)

echo [OK] pip found
echo.

REM Install dependencies
echo Installing required packages...
echo.

pip install -r requirements.txt

if %errorlevel% equ 0 (
    echo.
    echo [OK] Installation complete!
    echo.
    echo Next steps:
    echo 1. Add this server to your Claude Desktop config file
    echo 2. Restart Claude Desktop
    echo 3. Start asking about stocks!
    echo.
    echo See README.md for detailed configuration instructions.
) else (
    echo.
    echo [ERROR] Installation failed!
    echo Please check the error messages above and try again.
)

pause
