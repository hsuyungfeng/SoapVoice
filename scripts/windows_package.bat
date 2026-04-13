@echo off
REM SoapVoice Windows 打包批次檔
REM 此批次檔為 PowerShell 腳本的簡化版本，適合不熟悉 PowerShell 的使用者。

echo ========================================
echo SoapVoice Windows 自動打包腳本
echo ========================================
echo.
echo 請確保已安裝 PowerShell 5.1+（Windows 10/11 內建）。
echo.

REM 檢查 PowerShell 是否可用
powershell -Command "Write-Host '檢查 PowerShell 版本...' -ForegroundColor Cyan" >nul 2>&1
if errorlevel 1 (
    echo 錯誤：PowerShell 不可用，請確認 Windows PowerShell 已安裝。
    pause
    exit /b 1
)

REM 切換到腳本所在目錄
cd /d "%~dp0\.."

REM 詢問是否跳過 Inno Setup 編譯
set /p SKIP_INNO="是否跳過 Inno Setup 編譯？ (y/N): "
if /i "%SKIP_INNO%"=="y" (
    set ARGS="-SkipInnoSetup"
) else (
    set ARGS=
)

REM 執行 PowerShell 腳本
echo.
echo 正在執行 PowerShell 腳本...
echo 若出現「執行原則」錯誤，請以管理員身分執行：
echo   powershell -ExecutionPolicy Bypass -File scripts\windows_package.ps1 %ARGS%
echo.

powershell -ExecutionPolicy Bypass -File scripts\windows_package.ps1 %ARGS%

if errorlevel 1 (
    echo.
    echo 打包失敗，請檢查錯誤訊息。
    pause
    exit /b 1
)

echo.
echo 打包完成！請查看上方輸出訊息。
pause