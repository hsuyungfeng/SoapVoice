#!/usr/bin/env bash
# 測試覆蓋率執行腳本

set -e

echo "=========================================="
echo "SoapVoice 測試覆蓋率執行"
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

# 檢查是否安裝必要套件
check_dependencies() {
    log_info "檢查依賴..."
    if ! command -v uv &> /dev/null; then
        log_error "uv 未安裝"
        exit 1
    fi
}

# 執行測試覆蓋率
run_coverage() {
    log_info "執行測試覆蓋率..."
    
    cd "$(dirname "$0")/.."
    
    # 執行 pytest 並生成覆蓋率報告
    uv run pytest tests/ \
        --cov=src \
        --cov-report=html \
        --cov-report=term-missing \
        --cov-fail-under=80 \
        -v
    
    log_info "測試覆蓋率報告已生成："
    log_info "  HTML: htmlcov/index.html"
    log_info "  XML: coverage.xml"
}

# 顯示覆蓋率摘要
show_summary() {
    echo ""
    log_info "=========================================="
    log_info "測試覆蓋率摘要"
    log_info "=========================================="
    
    if [ -f "coverage.xml" ]; then
        log_info "覆蓋率報告已生成"
        log_info "查看 HTML 報告：open htmlcov/index.html"
    else
        log_warn "覆蓋率報告未生成"
    fi
}

# 主程式
main() {
    check_dependencies
    run_coverage
    show_summary
}

main "$@"
