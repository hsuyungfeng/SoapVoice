#!/usr/bin/env bash
# 部署驗證腳本

set -e

echo "=========================================="
echo "SoapVoice 部署驗證"
echo "=========================================="

# 顏色定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

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

# 檢查 Docker 服務
check_docker_services() {
    log_info "檢查 Docker 服務..."
    
    docker compose ps | grep -q "running" && return 0 || return 1
}

# 檢查 API 健康
check_api_health() {
    curl -s http://localhost:8000/health | grep -q "healthy" && return 0 || return 1
}

# 檢查 Ollama 服務
check_ollama() {
    curl -s http://localhost:11434/api/tags | grep -q "models" && return 0 || return 1
}

# 檢查模型
check_models() {
    ollama list | grep -q "qwen3.5" && return 0 || return 1
}

# 檢查 Redis
check_redis() {
    docker compose exec -T redis redis-cli ping | grep -q "PONG" && return 0 || return 1
}

# API 功能測試
test_normalize() {
    response=$(curl -s -X POST http://localhost:8000/api/v1/clinical/normalize \
        -H "Content-Type: application/json" \
        -d '{"text": "病人胸悶"}')
    
    echo "$response" | grep -q "normalized_text" && return 0 || return 1
}

test_icd10() {
    response=$(curl -s -X POST http://localhost:8000/api/v1/clinical/icd10 \
        -H "Content-Type: application/json" \
        -d '{"text": "病人胸悶，呼吸困難"}')
    
    echo "$response" | grep -q "matches" && return 0 || return 1
}

# 主程式
main() {
    echo ""
    log_info "開始部署驗證..."
    echo ""
    
    # Docker 服務檢查
    run_test "Docker 服務" "check_docker_services" || true
    
    # API 健康檢查
    run_test "API 健康檢查" "check_api_health" || true
    
    # Ollama 服務檢查
    run_test "Ollama 服務" "check_ollama" || true
    
    # 模型檢查
    run_test "模型檢查" "check_models" || true
    
    # Redis 檢查
    run_test "Redis 服務" "check_redis" || true
    
    # API 功能測試
    run_test "文本標準化 API" "test_normalize" || true
    run_test "ICD-10 分類 API" "test_icd10" || true
    
    # 總結
    echo ""
    echo "=========================================="
    echo "驗證摘要"
    echo "=========================================="
    echo "通過：$TESTS_PASSED"
    echo "失敗：$TESTS_FAILED"
    echo ""
    
    if [ $TESTS_FAILED -eq 0 ]; then
        log_info "所有部署驗證通過！系統已就緒。"
        echo ""
        echo "下一步:"
        echo "  1. 訪問測試頁面：http://localhost:8000/docs"
        echo "  2. 執行 beta 測試：./scripts/run_beta_test.sh"
        echo "  3. 查看監控儀表板：http://localhost:3000"
        exit 0
    else
        log_error "部分驗證失敗，請檢查上述錯誤。"
        exit 1
    fi
}

main "$@"
