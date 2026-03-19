#!/usr/bin/env bash
# 生產環境部署腳本 (簡化版)

set -e

echo "=========================================="
echo "SoapVoice 生產環境部署"
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

# 檢查前置條件
check_prerequisites() {
    log_info "檢查前置條件..."
    
    # 檢查 Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安裝"
        exit 1
    fi
    log_info "✓ Docker 已安裝"
    
    # 檢查 Docker Compose
    if ! command -v docker compose &> /dev/null; then
        log_error "Docker Compose 未安裝"
        exit 1
    fi
    log_info "✓ Docker Compose 已安裝"
    
    # 檢查 Ollama
    if ! command -v ollama &> /dev/null; then
        log_error "Ollama 未安裝"
        log_info "請先安裝 Ollama: curl -fsSL https://ollama.com/install.sh | sh"
        exit 1
    fi
    log_info "✓ Ollama 已安裝"
    
    # 檢查 Ollama 服務
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        log_warn "Ollama 服務未運行，嘗試啟動..."
        ollama serve &
        sleep 3
    fi
    log_info "✓ Ollama 服務運行中"
    
    # 檢查模型
    if ! ollama list | grep -q "qwen3.5"; then
        log_warn "qwen3.5 模型未安裝"
        log_info "請執行：ollama pull qwen3.5:9b"
    else
        log_info "✓ Qwen3.5 模型已安裝"
    fi
}

# 建立環境配置
setup_env() {
    log_info "建立環境配置..."
    
    if [ ! -f .env ]; then
        cp .env.example .env
        log_info "✓ .env 已建立"
        
        # 產生 JWT Secret Key
        JWT_SECRET=$(openssl rand -hex 32)
        sed -i "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$JWT_SECRET/" .env
        
        # 產生 API Key
        API_KEY=$(openssl rand -base64 32 | tr -d '\n')
        sed -i "s/DEFAULT_API_KEY=.*/DEFAULT_API_KEY=$API_KEY/" .env
        
        log_info "✓ JWT Secret Key 和 API Key 已產生"
    else
        log_info "✓ .env 已存在"
    fi
}

# 啟動服務
start_services() {
    log_info "啟動服務..."
    
    # 停止舊服務
    docker compose -f docker-compose.prod.yml down 2>/dev/null || true
    
    # 啟動新服務 (不使用需要認證的映像)
    docker compose -f docker-compose.prod.yml up -d --build
    
    log_info "✓ 服務已啟動"
    
    # 等待服務就緒
    log_info "等待服務就緒..."
    sleep 15
}

# 驗證部署
verify_deployment() {
    log_info "驗證部署..."
    
    # 檢查服務狀態
    docker compose -f docker-compose.prod.yml ps
    
    # 執行健康檢查
    if curl -s http://localhost:8000/health | grep -q "healthy"; then
        log_info "✓ API 健康檢查通過"
    else
        log_error "✗ API 健康檢查失敗"
        docker compose logs api
        exit 1
    fi
    
    # 檢查 Redis
    if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
        log_info "✓ Redis 服務正常"
    else
        log_warn "Redis 服務可能未就緒"
    fi
}

# 顯示部署資訊
show_info() {
    echo ""
    log_info "=========================================="
    log_info "部署完成！"
    log_info "=========================================="
    echo ""
    log_info "服務狀態:"
    docker compose -f docker-compose.prod.yml ps
    echo ""
    log_info "訪問方式:"
    echo "  API: http://localhost:8000"
    echo "  Swagger UI: http://localhost:8000/docs"
    echo "  ReDoc: http://localhost:8000/redoc"
    echo ""
    log_info "日誌:"
    echo "  docker compose logs -f api"
    echo "  docker compose logs -f redis"
    echo ""
    log_info "測試:"
    echo "  curl http://localhost:8000/health"
    echo "  ./scripts/deploy_verify.sh"
    echo ""
}

# 主程式
main() {
    check_prerequisites
    setup_env
    start_services
    verify_deployment
    show_info
}

main "$@"
