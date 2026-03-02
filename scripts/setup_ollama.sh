#!/usr/bin/env bash
# Ollama 模型設置腳本

set -e

echo "=========================================="
echo "Ollama 模型設置"
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

# 檢查 Ollama 是否安裝
check_ollama() {
    if command -v ollama &> /dev/null; then
        log_info "Ollama 已安裝"
        ollama --version
    else
        log_error "Ollama 未安裝"
        echo "請執行以下命令安裝 Ollama:"
        echo "  curl -fsSL https://ollama.com/install.sh | sh"
        exit 1
    fi
}

# 檢查 Ollama 服務是否運行
check_ollama_service() {
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        log_info "Ollama 服務運行中"
    else
        log_warn "Ollama 服務未運行，嘗試啟動..."
        ollama serve &
        sleep 3
    fi
}

# 列出可用模型
list_models() {
    log_info "可用模型:"
    ollama list
}

# 下載模型
pull_model() {
    local model=$1
    log_info "下載模型：$model"
    ollama pull "$model"
}

# 測試模型
test_model() {
    local model=$1
    log_info "測試模型：$model"
    echo "Q: 你好"
    ollama run "$model" "你好" | head -5
}

# 主程式
main() {
    echo ""
    check_ollama
    check_ollama_service
    
    echo ""
    log_info "開始設置 SoapVoice 所需模型..."
    
    # 模型清單
    MODELS=(
        "qwen3.5:35b"
        "qwen3.5:27b"
        "glm-4.7-flash:latest"
    )
    
    # 檢查已安裝的模型
    log_info "檢查已安裝的模型..."
    installed=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}')
    
    for model in "${MODELS[@]}"; do
        echo ""
        if echo "$installed" | grep -q "^${model}$"; then
            log_info "✓ 模型已安裝：$model"
        else
            log_warn "模型未安裝：$model"
            read -p "是否下載 $model? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                pull_model "$model"
            fi
        fi
    done
    
    echo ""
    log_info "模型設置完成!"
    echo ""
    list_models
    
    echo ""
    log_info "使用方式:"
    echo "  ollama run qwen3.5:35b"
    echo "  ollama run qwen3.5:27b"
    echo "  ollama run glm-4.7-flash:latest"
}

main "$@"
