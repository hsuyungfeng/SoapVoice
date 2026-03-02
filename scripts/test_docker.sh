#!/usr/bin/env bash
# Docker 環境部署測試腳本
# 用於驗證 Docker 和 Docker Compose 配置是否正確

set -e

echo "=========================================="
echo "SoapVoice Docker 部署測試"
echo "=========================================="

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 測試結果追蹤
TESTS_PASSED=0
TESTS_FAILED=0

# 輔助函數
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo "----------------------------------------"
    echo "測試：$test_name"
    
    if eval "$test_command"; then
        log_info "✓ $test_name 通過"
        ((TESTS_PASSED++))
        return 0
    else
        log_error "✗ $test_name 失敗"
        ((TESTS_FAILED++))
        return 1
    fi
}

# 檢查 Docker 是否安裝
run_test "Docker 安裝檢查" "docker --version"

# 檢查 Docker Compose 是否安裝
run_test "Docker Compose 安裝檢查" "docker compose version"

# 檢查 NVIDIA Docker 是否安裝
run_test "NVIDIA Docker 檢查" "docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi"

# 檢查 docker-compose.yml 是否存在
run_test "docker-compose.yml 存在檢查" "test -f docker-compose.yml"

# 檢查 Dockerfile 是否存在
run_test "Dockerfile 存在檢查" "test -f Dockerfile"

# 驗證 docker-compose.yml 語法
run_test "docker-compose.yml 語法檢查" "docker compose config"

# 檢查 .env 檔案（可選）
if [ -f .env ]; then
    log_info ".env 檔案存在"
else
    log_warn ".env 檔案不存在，使用預設值"
fi

# 建立測試用 .env 檔案
if [ ! -f .env.test ]; then
    log_info "建立測試用 .env.test 檔案"
    cat > .env.test << EOF
# 測試環境配置
PYTHONUNBUFFERED=1
DEV_MODE=false
INITIALIZE_LLM=false
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
LLM_MODEL=Qwen/Qwen3-32B-Instruct
LLM_GPU_MEMORY=0.9
HF_TOKEN=${HF_TOKEN:-}
EOF
fi

echo "=========================================="
echo "Docker 部署測試摘要"
echo "=========================================="
echo "通過：$TESTS_PASSED"
echo "失敗：$TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    log_info "所有 Docker 部署測試通過！"
    echo ""
    echo "下一步："
    echo "1. 複製 .env.test 為 .env 並調整配置"
    echo "2. 執行 'docker compose build' 建立映像"
    echo "3. 執行 'docker compose up -d' 啟動服務"
    echo "4. 訪問 http://localhost:8000/docs 查看 API 文件"
    exit 0
else
    log_error "部分 Docker 部署測試失敗，請檢查上述錯誤"
    exit 1
fi
