#!/bin/bash
# SoapVoice 啟動腳本

echo "================================================"
echo "🎤 SoapVoice - 醫療語音轉 SOAP 病歷系統"
echo "================================================"

# 檢查是否在虛擬環境中
if [ -z "$VIRTUAL_ENV" ] && [ -d ".venv" ]; then
    echo "🔧 啟動虛擬環境..."
    source .venv/bin/activate
fi

# 檢查必要套件
echo "🔍 檢查必要套件..."
if ! command -v uv &> /dev/null; then
    echo "❌ uv 未安裝"
    echo "💡 請先安裝 uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 安裝必要套件
echo "📦 安裝/更新套件..."
uv sync --quiet

# 檢查端口
echo "🔌 檢查端口..."
if lsof -i :8000 &> /dev/null; then
    echo "⚠️  端口 8000 已被佔用"
    echo "💡 嘗試關閉佔用進程..."
    lsof -ti :8000 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

# 設定音訊環境變數（避免 ALSA 錯誤）
export PULSE_SERVER=unix:/tmp/pulse.socket
export ALSA_CARD=0

# 啟動系統
echo "🚀 啟動 SoapVoice..."
echo "================================================"

# 使用改進的啟動腳本
python start_gui.py

echo ""
echo "================================================"
echo "👋 SoapVoice 已結束"
echo "================================================"