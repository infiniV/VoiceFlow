@echo off
REM Dictore Installer Build Script
REM Requires: Inno Setup 6 installed (https://jrsoftware.org/isdl.php)

setlocal

REM Check if Inno Setup is installed
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if "%ISCC%"=="" (
    echo Error: Inno Setup 6 not found!
    echo Please install from: https://jrsoftware.org/isdl.php
    exit /b 1
)

REM Check if build output exists
if not exist "..\dist\Dictore" (
    echo Error: PyInstaller output not found at ..\dist\Dictore
    echo Please run 'pnpm run build' first.
    exit /b 1
)

REM Create output directory
if not exist "..\dist\installer" mkdir "..\dist\installer"

REM Build installer
echo Building Dictore installer...
"%ISCC%" dictore.iss

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Success! Installer created at: dist\installer\
    dir "..\dist\installer\*.exe"
) else (
    echo.
    echo Error: Installer build failed!
    exit /b 1
)

endlocal
