#!/bin/bash
# 完整模型測試腳本
# 需先安裝依賴: pip install faster-whisper pytesseract pillow easyocr paddleocr

echo "=========================================="
echo "SoapVoice 完整模型測試"
echo "=========================================="
echo ""

# 檢查系統資訊
echo "=== 系統資訊 ==="
echo "CPU cores: $(nproc)"
echo "RAM: $(free -h | awk '/^Mem:/ {print $2}')"
echo ""

# 檢查可用模型
echo "=== 可用模型 ==="
echo ""
echo "1. Ollama 模型 (如已運行):"
curl -s http://localhost:11434/api/tags 2>/dev/null | jq -r '.models[].name' 2>/dev/null || echo "  (Ollama 未運行)"
echo ""
echo "2. GGUF 模型:"
find ~ -name "*.gguf" -type f 2>/dev/null | grep -v vocab | head -10 | while read f; do
    size=$(du -h "$f" | cut -f1)
    echo "  - $(basename "$f") ($size)"
done
echo ""

# 檢查 OCR 工具
echo "=== OCR 工具 ==="
which tesseract 2>/dev/null && echo "  ✓ Tesseract: $(tesseract --version 2>&1 | head -1)" || echo "  ✗ Tesseract 未安裝"
echo ""

# 測試項目
echo "=== 測試項目 ==="
echo "1. ASR - Whisper 語音轉文字"
echo "2. LLM - gemma4:e4b / qwen2.5:7b SOAP 生成"
echo "3. OCR - PaddleOCR/Tesseract 螢幕截圖"
echo ""

# 測試音檔
echo "=== 測試音檔 ==="
ls -la static/*.wav 2>/dev/null | awk '{print "  " $NF " (" int($5/1024) "KB)"}'
echo ""

echo "=========================================="
echo "開始測試..."
echo "=========================================="

# 執行 Python 測試
cd /home/hsu/Desktop/SoapVoice
python3 scripts/test_all_models.py 2>&1
