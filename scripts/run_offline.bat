@echo off
REM SoapVoice Windows Offline Deployment Script
REM 使用 llama.cpp + GGUF 模型，完全離線運行

echo ========================================
echo SoapVoice Offline Launcher (Windows)
echo ========================================
echo.

REM 設定路徑
set SCRIPT_DIR=%~dp0
set MODELS_DIR=%SCRIPT_DIR%models
set LLM_MODEL=%MODELS_DIR%\Qwen2.5-7B-Instruct-Q4_K_M.gguf
set LLM_MODEL_3B=%MODELS_DIR%\qwen2.5-3b-instruct-q4_k_m.gguf

REM 檢查模型檔案
echo [1/4] 檢查模型檔案...
if exist "%LLM_MODEL%" (
    echo   - Qwen2.5-7B: OK
) else (
    echo   - Qwen2.5-7B: NOT FOUND - 請下載 Qwen2.5-7B-Instruct-Q4_K_M.gguf
)

if exist "%LLM_MODEL_3B%" (
    echo   - Qwen2.5-3B: OK
) else (
    echo   - Qwen2.5-3B: NOT FOUND
)

REM 檢查 llama.cpp
echo.
echo [2/4] 檢查 llama.cpp...
if exist "%SCRIPT_DIR%models\windows\llama-cli.exe" (
    echo   - llama-cli.exe: OK
) else (
    echo   - llama-cli.exe: NOT FOUND
)

REM 啟動 llama.cpp server
echo.
echo [3/4] 啟動 llama.cpp server...
set LLAVA_MODEL=none
set PORT=8080

REM 使用 7B 模型
"%SCRIPT_DIR%models\windows\llama-server.exe" -m "%LLM_MODEL%" -c 2048 -n 512 --temp 0.3 -ngl 0 --port %PORT% --host 0.0.0.0

echo.
echo [4/4] Server 啟動完成
echo.
echo 請開啟瀏覽器訪問: http://localhost:%PORT%
echo 按 Ctrl+C 停止伺服器
pause