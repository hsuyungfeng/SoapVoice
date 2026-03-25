@echo off
REM SoapVoice Windows 部署腳本
REM 支援 CPU-only 與 GPU 兩種模式

setlocal enabledelayedexpansion

REM ========================================
REM 配置區域 - 請根據需要修改
REM ========================================

set "DOCKER_IMAGE=soapvoice/api:latest"
set "CONTAINER_NAME=soapvoice"
set "API_PORT=8000"

REM 預設模式
set "MODE=GPU"

REM ========================================
REM 解析命令行參數
REM ========================================

:parse_args
if "%~1"=="" goto done_args
if /i "%~1"=="--cpu" (
    set "MODE=CPU"
    shift
    goto parse_args
)
if /i "%~1"=="--gpu" (
    set "MODE=GPU"
    shift
    goto parse_args
)
if /i "%~1"=="--build" (
    set "BUILD=1"
    shift
    goto parse_args
)
if /i "%~1"=="--help" goto show_help
echo 未知參數: %~1
goto show_help

:done_args

REM ========================================
REM 顯示幫助
REM ========================================

:show_help
echo.
echo SoapVoice Windows 部署腳本
echo.
echo 使用方式:
echo   deploy.bat [選項]
echo.
echo 選項:
echo   --cpu      使用 CPU-only 模式（無 GPU）
echo   --gpu      使用 GPU 模式（需要 NVIDIA GPU）
echo   --build    重新建置 Docker 映像
echo   --help     顯示此幫助
echo.
echo 範例:
echo   deploy.bat --gpu           使用 GPU 模式運行
echo   deploy.bat --cpu           使用 CPU 模式運行
echo   deploy.bat --cpu --build   CPU 模式並重新建置
echo.
exit /b 0

REM ========================================
REM 主程式
REM ========================================

echo.
echo ========================================
echo SoapVoice 部署 (Mode: %MODE%)
echo ========================================

REM 檢查 Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 未找到 Docker，請先安裝 Docker Desktop
    exit /b 1
)

REM 停止現有容器
echo.
echo [1/4] 停止現有容器...
docker stop %CONTAINER_NAME% >nul 2>&1
docker rm %CONTAINER_NAME% >nul 2>&1

REM 建置映像（如果需要）
if defined BUILD (
    echo.
    echo [2/4] 建置 Docker 映像...
    docker build -t %DOCKER_IMAGE% .
    if errorlevel 1 (
        echo [錯誤] Docker 建置失敗
        exit /b 1
    )
)

REM 運行容器
echo.
echo [3/4] 啟動容器...

if /i "%MODE%"=="CPU" (
    echo   模式: CPU-only
    docker run -d ^
        --name %CONTAINER_NAME% ^
        -p %API_PORT%:8000 ^
        -e PYTHONUNBUFFERED=1 ^
        -e OLLAMA_HOST=host.docker.internal:11434 ^
        -e LLM_MODEL=qwen2.5:3b ^
        --network host ^
        %DOCKER_IMAGE% ^
        uvicorn src.main:app --host 0.0.0.0 --port 8000

    echo.
    echo [提示] CPU 模式需要本機運行 Ollama
    echo   請確保 Ollama 已啟動: ollama serve
    echo   或者使用 Docker Compose: docker-compose up ollama

) else (
    echo   模式: GPU
    docker run -d ^
        --name %CONTAINER_NAME% ^
        -p %API_PORT%:8000 ^
        --gpus all ^
        -e PYTHONUNBUFFERED=1 ^
        -e OLLAMA_HOST=ollama:11434 ^
        -e LLM_MODEL=qwen2.5:7b ^
        --network soapvoice-net ^
        %DOCKER_IMAGE% ^
        uvicorn src.main:app --host 0.0.0.0 --port 8000
)

if errorlevel 1 (
    echo [錯誤] 容器啟動失敗
    exit /b 1
)

REM 等待並檢查狀態
echo.
echo [4/4] 檢查服務狀態...
timeout /t 5 /nobreak >nul

REM 嘗試訪問健康檢查
curl -s -o nul -w "%%{http_code}" http://localhost:%API_PORT%/health >tmp.txt 2>&1
set /p STATUS=<tmp.txt
del tmp.txt

if "%STATUS%"=="200" (
    echo.
    echo ========================================
    echo 部署成功！
    echo ========================================
    echo.
    echo API 地址: http://localhost:%API_PORT%
    echo API 文件: http://localhost:%API_PORT%/docs
    echo.
) else (
    echo.
    echo [警告] 服務可能尚未完全啟動
    echo   請稍後檢查: docker logs %CONTAINER_NAME%
)

echo.
echo 其他常用命令:
echo   查看日誌:   docker logs -f %CONTAINER_NAME%
echo   停止服務:   docker stop %CONTAINER_NAME%
echo   重新啟動:   docker restart %CONTAINER_NAME%
echo.

endlocal
exit /b 0