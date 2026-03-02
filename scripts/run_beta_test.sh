#!/usr/bin/env bash
# 醫師 Beta 測試執行腳本

set -e

echo "=========================================="
echo "SoapVoice 醫師 Beta 測試執行"
echo "=========================================="

# 顏色定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 檢查 API 服務是否運行
check_api() {
    log_info "檢查 API 服務..."
    
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        log_info "✓ API 服務運行中"
    else
        log_error "✗ API 服務未運行"
        log_info "請執行：uv run uvicorn src.main:app --host 0.0.0.0 --port 8000"
        exit 1
    fi
}

# 檢查 Ollama 服務是否運行
check_ollama() {
    log_info "檢查 Ollama 服務..."
    
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        log_info "✓ Ollama 服務運行中"
        
        # 顯示可用模型
        log_info "可用模型:"
        ollama list 2>/dev/null | head -5
    else
        log_warn "Ollama 服務未運行"
        log_info "請執行：ollama serve"
    fi
}

# 顯示測試場景
show_test_scenarios() {
    echo ""
    log_info "=========================================="
    log_info "測試場景"
    log_info "=========================================="
    
    cat << EOF

場景 1: 門診病歷記錄
  - 使用語音輸入病歷
  - 系統即時轉錄並生成 SOAP
  - 醫師檢視並調整 SOAP 內容
  
場景 2: 急診快速記錄
  - 快速語音記錄
  - 系統即時生成初步病歷
  - 醫師補充關鍵資訊

場景 3: 複雜病例記錄
  - 多症狀、多系統病例
  - 系統整合多項資訊
  - 生成完整 SOAP 病歷

EOF
}

# 執行端到端測試
run_e2e_test() {
    log_info "執行端到端測試..."
    
    uv run python scripts/test_e2e.py
}

# 顯示測試頁面
show_test_page() {
    echo ""
    log_info "=========================================="
    log_info "測試頁面"
    log_info "=========================================="
    log_info "開啟測試頁面：open docs/test-page.html"
    log_info "或訪問：http://localhost:8000/docs"
}

# 主程式
main() {
    check_api
    check_ollama
    show_test_scenarios
    run_e2e_test
    show_test_page
    
    echo ""
    log_info "=========================================="
    log_info "Beta 測試準備完成！"
    log_info "=========================================="
    echo ""
    log_info "下一步:"
    echo "  1. 邀請醫師參與測試"
    echo "  2. 發放測試帳號和 API Key"
    echo "  3. 收集回饋表單 (docs/BETA_TEST_FEEDBACK.md)"
    echo "  4. 分析測試結果"
    echo ""
}

main "$@"
