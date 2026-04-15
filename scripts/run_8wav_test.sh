#!/bin/bash
# SoapVoice 8-WAV 測試自動化腳本

MODEL=${1:-"qwen2.5:7b"}
PORT=8000

echo "============================================"
echo " SoapVoice 8-WAV 自動化測試"
echo " 模型: $MODEL"
echo "============================================"

# 1. 檢查伺服器是否已啟動
if ! curl -s http://localhost:$PORT/api/v1/clinical/health > /dev/null; then
    echo "🚀 啟動伺服器..."
    uv run uvicorn src.main:app --host 0.0.0.0 --port $PORT > server_test.log 2>&1 &
    SERVER_PID=$!
    echo "⏱️ 等待伺服器就緒 (30s)..."
    sleep 30
else
    echo "✅ 伺服器已在運行中"
fi

# 2. 執行測試
echo "🧪 開始執行基準測試..."
uv run python scripts/compare_detailed.py "$MODEL"

# 3. 檢查結果
RESULT_FILE="tests/fixtures/results/${MODEL//:/_}_results.json"
if [ -f "$RESULT_FILE" ]; then
    echo "✅ 測試完成！結果已儲存至: $RESULT_FILE"
else
    echo "❌ 測試失敗，未找到結果檔案。"
fi

# 4. 如果是腳本啟動的伺服器，則關閉它 (可選)
# if [ ! -z "$SERVER_PID" ]; then
#     kill $SERVER_PID
#     echo "🛑 伺服器已關閉"
# fi

echo "============================================"
