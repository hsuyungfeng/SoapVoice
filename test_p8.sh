#!/bin/bash
cd "$(dirname "$0")"

echo "=== 啟動 SoapVoice 後端伺服器 ==="
USE_LLAMA_CPP=true uv run uvicorn src.main:app --host 0.0.0.0 --port 8010 --log-level warning > server_test.log 2>&1 &
SERVER_PID=$!
echo "伺服器 PID: $SERVER_PID"

# 等待伺服器啟動
echo "等待伺服器啟動..."
sleep 5

# 檢查健康端點
echo "=== 測試健康端點 ==="
if ! curl -s http://localhost:8010/health > /dev/null; then
    echo "❌ 健康檢查失敗"
    cat server_test.log
    kill $SERVER_PID 2>/dev/null
    exit 1
fi
echo "✅ 健康檢查通過"

# 測試音訊轉錄
echo "=== 測試音訊轉錄端點 ==="
TRANSCRIPT_RESPONSE=$(curl -s -X POST http://localhost:8010/api/v1/extended/transcribe \
    -F "audio_path=data/recordings/temp.wav")
echo "轉錄回應: $TRANSCRIPT_RESPONSE"

# 檢查轉錄是否成功
if echo "$TRANSCRIPT_RESPONSE" | grep -q "transcript"; then
    echo "✅ 音訊轉錄成功"
    # 提取轉錄文字
    TRANSCRIPT=$(echo "$TRANSCRIPT_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['transcript'])" 2>/dev/null)
    if [ -z "$TRANSCRIPT" ]; then
        TRANSCRIPT="病人主訴頭痛三天，伴隨噁心嘔吐，體溫38.5度。"
        echo "⚠️  無法解析 JSON，使用預設轉錄文字: $TRANSCRIPT"
    fi
else
    echo "❌ 音訊轉錄失敗"
    echo "回應: $TRANSCRIPT_RESPONSE"
    TRANSCRIPT="病人主訴頭痛三天，伴隨噁心嘔吐，體溫38.5度。"
    echo "使用預設轉錄文字: $TRANSCRIPT"
fi

# 測試完整擴展流程
echo "=== 測試完整擴展流程端點 ==="
PROCESS_RESPONSE=$(curl -s -X POST http://localhost:8010/api/v1/extended/process \
    -H "Content-Type: application/json" \
    -d "{\"transcript\": \"$TRANSCRIPT\", \"model\": \"qwen2.5:7b\", \"include_symptoms\": true, \"include_icd10\": true, \"include_orders\": true, \"include_drugs\": true, \"output_lang\": \"en\"}")
echo "流程回應: $PROCESS_RESPONSE"

# 檢查回應是否包含必要欄位
if echo "$PROCESS_RESPONSE" | grep -q "icd10_codes"; then
    echo "✅ ICD-10 代碼存在"
else
    echo "❌ ICD-10 代碼缺失"
fi

if echo "$PROCESS_RESPONSE" | grep -q "medical_orders"; then
    echo "✅ 醫囑建議存在"
else
    echo "❌ 醫囑建議缺失"
fi

if echo "$PROCESS_RESPONSE" | grep -q "drug_recommendations"; then
    echo "✅ 藥物建議存在"
else
    echo "❌ 藥物建議缺失"
fi

if echo "$PROCESS_RESPONSE" | grep -q "soap"; then
    echo "✅ SOAP 病歷存在"
else
    echo "❌ SOAP 病歷缺失"
fi

# 顯示伺服器日誌
echo "=== 伺服器日誌 ==="
cat server_test.log

# 停止伺服器
echo "=== 停止伺服器 ==="
kill $SERVER_PID 2>/dev/null && echo "伺服器已停止" || echo "停止伺服器失敗"

exit 0