# 🎤 SoapVoice 錄音測試指南

**版本:** v1.0  
**日期:** 2026-03-15  
**適用環境:** 開發環境 / 生產環境

---

## 📋 測試項目

### 1. 語音錄製測試

#### 1.1 使用 WebSocket 測試頁面

**步驟:**

1. 開啟測試頁面
```bash
# 訪問 WebSocket 測試頁面
open http://localhost:8000/docs
```

2. 連接 WebSocket
```
端點：/api/v1/ws/transcribe
方法：WebSocket
```

3. 發送測試訊息
```json
{
  "type": "start",
  "client_id": "test_001"
}
```

4. 發送音頻塊
```json
{
  "type": "chunk",
  "data": {
    "audio": "<base64 編碼的音頻數據>"
  }
}
```

5. 結束錄製
```json
{
  "type": "end"
}
```

#### 1.2 使用 Python 測試腳本

```bash
# 執行錄音測試腳本
uv run python scripts/test_recording.py
```

---

### 2. 語音轉文字測試

#### 2.1 測試範例文本

**範例 1: 門診病歷**
```
病人說他胸悶兩天，還有點喘。
血壓 140/90，心跳每分 80 下。
初步診斷為高血壓，開藥三天後回診。
```

**範例 2: 急診病歷**
```
病人跌倒後右膝蓋紅腫疼痛。
X 光檢查無骨折。
診斷為軟組織挫傷，建議冰敷休息。
```

**範例 3: 複雜病歷**
```
病人主訴頭痛三天，伴隨噁心嘔吐。
血壓 160/100，有高血压病史。
神經學檢查正常。
疑似偏頭痛，給予止痛藥。
```

#### 2.2 執行測試

```bash
# 使用測試腳本
uv run python scripts/test_voice_to_text.py
```

---

### 3. SOAP 生成測試

#### 3.1 測試命令

```bash
# 測試 SOAP 生成
curl -X POST http://localhost:8000/api/v1/clinical/soap/generate \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "病人胸悶兩天，呼吸困難，血壓 140/90",
    "patient_context": {
      "age": 45,
      "gender": "M"
    }
  }'
```

#### 3.2 預期輸出

```json
{
  "soap": {
    "subjective": "45-year-old male with chest tightness for 2 days...",
    "objective": "BP: 140/90...",
    "assessment": "R07.89 - Chest tightness...",
    "plan": "Further evaluation pending...",
    "conversation_summary": "病人主訴胸悶兩天伴隨呼吸困難..."
  },
  "metadata": {...},
  "processing_time_ms": 1234.5
}
```

---

## 🧪 自動化測試腳本

### test_recording.py

```python
#!/usr/bin/env python3
"""
錄音測試腳本

測試 WebSocket 語音串流功能
"""

import asyncio
import websockets
import json
import base64
import pyaudio

async def test_recording():
    """測試錄音功能"""
    
    uri = "ws://localhost:8000/api/v1/ws/transcribe"
    
    async with websockets.connect(uri) as websocket:
        # 發送開始訊息
        await websocket.send(json.dumps({
            "type": "start",
            "client_id": "test_001"
        }))
        
        # 接收確認
        response = await websocket.recv()
        print(f"服務器回應：{response}")
        
        # 錄製音頻 (模擬)
        # 實際使用時需要連接麥克風
        print("開始錄音...")
        
        # 發送音頻塊 (此處為示例)
        # audio_data = record_audio_chunk()
        # await websocket.send(json.dumps({
        #     "type": "chunk",
        #     "data": {"audio": base64.b64encode(audio_data).decode()}
        # }))
        
        # 發送結束訊息
        await websocket.send(json.dumps({
            "type": "end"
        }))
        
        # 接收最終結果
        result = await websocket.recv()
        print(f"轉錄結果：{result}")

if __name__ == "__main__":
    asyncio.run(test_recording())
```

---

## 📊 測試評估標準

### 語音辨識準確率

| 指標 | 目標 | 測量方式 |
|------|------|----------|
| 詞錯誤率 (WER) | <5% | (S+D+I)/N |
| 句錯誤率 (SER) | <10% | 錯誤句子數/總句子數 |
| 醫療術語辨識率 | ≥95% | 正確辨識的醫療術語數/總醫療術語數 |

**說明:**
- S: 替換 (Substitution)
- D: 刪除 (Deletion)
- I: 插入 (Insertion)
- N: 總詞數

### 效能指標

| 指標 | 目標 | 測量方式 |
|------|------|----------|
| 首字延遲 | <500ms | 發送音頻到收到第一個字的時間 |
| 端到端延遲 | <3s | 發送完整音頻到收到完整轉錄的時間 |
| 並發支援 | ≥10 | 同時連接的 WebSocket 數量 |

---

## 🔧 問題排查

### 問題 1: WebSocket 連接失敗

**可能原因:**
- 服務未啟動
- 端口被防火牆阻擋
- WebSocket 路徑錯誤

**解決方案:**
```bash
# 檢查服務狀態
curl http://localhost:8000/health

# 檢查防火牆
sudo ufw status

# 測試 WebSocket
uv run python scripts/test_websocket.py
```

### 問題 2: 音頻無法辨識

**可能原因:**
- 音頻格式不正確
- 採樣率不匹配
- 音量過低

**解決方案:**
- 確保音頻格式為 PCM 16-bit
- 採樣率設為 16000 Hz
- 調整麥克風音量

### 問題 3: 轉錄結果不準確

**可能原因:**
- 背景噪音
- 發音不清晰
- 醫療術語未收錄

**解決方案:**
- 在安靜環境錄音
- 清晰發音
- 更新醫療詞彙庫

---

## 📝 測試記錄表

| 測試日期 | 測試人員 | 測試場景 | WER | SER | 備註 |
|----------|----------|----------|-----|-----|------|
| 2026-03-15 | | 門診病歷 | | | |
| 2026-03-15 | | 急診病歷 | | | |
| 2026-03-15 | | 複雜病歷 | | | |

---

## 🎯 下一步

1. 執行自動化測試腳本
2. 收集測試數據
3. 分析 WER 和 SER
4. 優化模型和詞彙庫
5. 重複測試直到達標

---

**測試愉快！** 🎤
