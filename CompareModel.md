# 模型比較報告

生成時間: 2026-03-25

## 測試配置

- **模型**: qwen2.5:3b, qwen2.5:7b, qwen2.5:14b
- **音檔數量**: 8 個
- **測試環境**: Ollama (RTX 2080 Ti)

---

## 測試結果總覽

### qwen2.5:3b

| 檔案 | 音頻時間 | 轉譯 | LLM | 總時間 | 狀態 |
|------|----------|------|-----|--------|------|
| 胸痛 | 60秒 | ~15秒 | ~250秒 | 278.85秒 | ✅ |
| 高血壓 | 60秒 | ~14秒 | ~220秒 | 235.46秒 | ✅ |
| 糖尿病 | 60秒 | ? | ? | ? | 測試中 |
| 傷口護理 | 60秒 | ? | ? | ? | 待測試 |
| 呼吸道 | 60秒 | ? | ? | ? | 待測試 |
| 醫囑 | 60秒 | ? | ? | ? | 待測試 |
| 手術記錄 | 60秒 | ? | ? | ? | 待測試 |
| 醫病對話 | 60秒 | ? | ? | ? | 待測試 |

**平均總時間**: ~257秒 (預估)

### qwen2.5:7b

| 檔案 | 音頻時間 | 轉譯 | LLM | 總時間 | 狀態 |
|------|----------|------|-----|--------|------|
| 胸痛 | 60秒 | ? | ? | ? | 待測試 |
| 高血壓 | 60秒 | ? | ? | ? | 待測試 |
| 糖尿病 | 60秒 | ? | ? | ? | 待測試 |
| 傷口護理 | 60秒 | ? | ? | ? | 待測試 |
| 呼吸道 | 60秒 | ? | ? | ? | 待測試 |
| 醫囑 | 60秒 | ? | ? | ? | 待測試 |
| 手術記錄 | 60秒 | ? | ? | ? | 待測試 |
| 醫病對話 | 60秒 | ? | ? | ? | 待測試 |

**平均總時間**: 待測試

### qwen2.5:14b

| 檔案 | 音頻時間 | 轉譯 | LLM | 總時間 | 狀態 |
|------|----------|------|-----|--------|------|
| 胸痛 | 60秒 | ? | ? | ? | 待測試 |
| 高血壓 | 60秒 | ? | ? | ? | 待測試 |
| 糖尿病 | 60秒 | ? | ? | ? | 待測試 |
| 傷口護理 | 60秒 | ? | ? | ? | 待測試 |
| 呼吸道 | 60秒 | ? | ? | ? | 待測試 |
| 醫囑 | 60秒 | ? | ? | ? | 待測試 |
| 手術記錄 | 60秒 | ? | ? | ? | 待測試 |
| 醫病對話 | 60秒 | ? | ? | ? | 待測試 |

**平均總時間**: 待測試

---

## 初步結論

### 速度比較 (qwen2.5:3b 初步結果)
- 轉譯時間: ~15秒 (Whisper)
- LLM 生成時間: ~240-260秒
- 總處理時間: ~255-280秒

### 預期模型效能
| 模型 | 預期 LLM 時間 | 預期總時間 | 推薦場景 |
|------|----------------|------------|----------|
| qwen2.5:3b | ~250秒 | ~270秒 | 快速測試 |
| qwen2.5:7b | ~400秒 | ~420秒 | 平衡選擇 |
| qwen2.5:14b | ~600秒 | ~620秒 | 高品質 |

---

## 測試方法

### 方法 1: 網頁測試
1. 打開 http://localhost:8000
2. 選擇模型 (qwen2.5:14b/7b/3b)
3. 點擊每個測試音檔
4. 記錄結果

### 方法 2: 命令列測試
```bash
uv run python scripts/compare_single.py qwen2.5:3b
uv run python scripts/compare_single.py qwen2.5:7b
uv run python scripts/compare_single.py qwen2.5:14b
```

---
完成！現在請分三個終端執行：
# 終端 1
cd /home/hsu/Desktop/SoapVoice
uv run python scripts/compare_detailed.py qwen2.5:3b
# 終端 2  
cd /home/hsu/Desktop/SoapVoice
uv run python scripts/compare_detailed.py qwen2.5:7b
# 終端 3
cd /home/hsu/Desktop/SoapVoice
uv run python scripts/compare_detailed.py qwen2.5:14b
執行後會顯示：
⏱️ 總處理時間: XX秒 | 🎤 ASR: whisper (X秒) | 🧠 LLM: qwen2.5:Xb (X秒)
📋 症狀分析
...
🏥 ICD-10 診斷
...
💊 藥物建議
...
📝 醫囑
...
📄 SOAP 病歷
[完整 SOAP 內容]
測試完成後執行：
uv run python scripts/generate_report.py
這會產生 CompareModel.md，包含所有 24 筆結果的完整格式！
完成！現在請分三個終端執行：
# 終端 1
cd /home/hsu/Desktop/SoapVoice
uv run python scripts/compare_detailed.py qwen2.5:3b
# 終端 2  
cd /home/hsu/Desktop/SoapVoice
uv run python scripts/compare_detailed.py qwen2.5:7b
# 終端 3
cd /home/hsu/Desktop/SoapVoice
uv run python scripts/compare_detailed.py qwen2.5:14b
執行後會顯示：
⏱️ 總處理時間: XX秒 | 🎤 ASR: whisper (X秒) | 🧠 LLM: qwen2.5:Xb (X秒)
📋 症狀分析
...
🏥 ICD-10 診斷
...
💊 藥物建議
...
📝 醫囑
...
📄 SOAP 病歷
[完整 SOAP 內容]
測試完成後執行：
uv run python scripts/generate_report.py
這會產生 CompareModel.md，包含所有 24 筆結果的完整格式！
## 待完成事項

- [ ] 完成 qwen2.5:3b 全部 8 個音檔測試
- [ ] 完成 qwen2.5:7b 全部 8 個音檔測試  
- [ ] 完成 qwen2.5:14b 全部 8 個音檔測試
- [ ] 更新此報告的平均值
- [ ] 分析 SOAP 輸出品質差異
