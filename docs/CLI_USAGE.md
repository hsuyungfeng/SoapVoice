# SoapVoice CLI 使用指南

## 簡介

SoapVoice CLI 是一個命令列互動介面，讓使用者可以輸入醫療對話並使用較小模型（預設 `qwen3.5:9b`）生成 SOAP 病歷記錄。

## 安裝與設定

### 1. 確保環境就緒

```bash
# 安裝依賴
uv sync

# 確認 Ollama 服務運行中
ollama serve

# 下載模型（如果尚未下載）
ollama pull qwen3.5:9b
ollama pull qwen3.5:27b  # 備用模型
```

### 2. 設定執行權限

```bash
chmod +x src/cli.py
```

## 使用方式

### 互動模式（推薦）

```bash
# 基本互動模式
uv run python src/cli.py

# 使用備用模型
uv run python src/cli.py --model qwen3.5:27b

# 顯示詳細日誌
uv run python src/cli.py --verbose
```

**互動模式流程：**
1. 輸入醫療對話內容（多行輸入，空行結束）
2. 輸入病患背景資訊（可選）
3. 系統自動進行術語標準化
4. 生成 SOAP 病歷並顯示結果
5. 詢問是否繼續處理另一筆對話

### 檔案模式

```bash
# 從檔案讀取對話
uv run python src/cli.py --file examples/cli_example_input.txt

# 指定病患資訊
uv run python src/cli.py --file input.txt --age 45 --gender M --chief-complaint "胸悶兩天"
```

### 文字模式

```bash
# 直接輸入對話文字
uv run python src/cli.py --text "病人胸悶兩天呼吸困難" --age 45 --gender M
```

## 輸出範例

```
============================================================
✅ SOAP 病歷生成完成
============================================================

📝 SOAP 病歷:
----------------------------------------
S (主觀陳述):
45-year-old male presents with chest tightness and dyspnea for two days...

O (客觀發現):
Respiratory auscultation reveals coarse breath sounds without obvious rales...

A (評估):
Acute bronchitis, possible asthma exacerbation. ICD-10: J20.9, R07.89

P (計畫):
Prescribe bronchodilator, follow up if symptoms persist...

💬 對話摘要 (繁體中文):
45歲男性患者主訴胸悶和呼吸困難兩天...

🔍 術語標準化:
  • 胸悶 → chest tightness (R07.89)
  • 呼吸困難 → dyspnea (R06.02)

📊 分類置信度:
  subjective     ███████████████████░ 95.0%
  objective      █████████████████░░░ 85.0%
  assessment     ████████████████░░░░ 80.0%
  plan           ██████████████████░░ 90.0%
```

## 功能特色

### 1. 術語標準化
- 自動將口語中文轉換為標準醫療英文術語
- 顯示 ICD-10 候選碼
- 失敗時自動 fallback 使用原始文字

### 2. 多模型支援
- 主力模型：`qwen3.5:9b`（VRAM 需求低、推理快）
- 備用模型：`qwen3.5:27b`（品質更高）
- 可自定義其他 Ollama 模型

### 3. 病患背景整合
- 年齡、性別、主訴等背景資訊
- 自動整合到 SOAP 生成提示詞中

### 4. 視覺化輸出
- 彩色標記的 SOAP 段落
- 術語標準化結果
- 分類置信度條形圖
- 繁體中文對話摘要

## 進階設定

### 自定義 API 端點

```bash
# 使用自定義 Ollama API
uv run python src/cli.py --api-base http://192.168.1.100:11434
```

### 批次處理

```bash
#!/bin/bash
# 批次處理多個檔案
for file in data/transcripts/*.txt; do
    echo "處理: $file"
    uv run python src/cli.py --file "$file" --age 50 --gender F
    echo ""
done
```

## 疑難排解

### 常見問題

1. **Ollama 服務未運行**
   ```
   ❌ 初始化失敗: Connection refused
   ```
   **解決方案：** 執行 `ollama serve`

2. **模型未下載**
   ```
   ❌ SOAP 生成失敗: Model not found
   ```
   **解決方案：** 執行 `ollama pull qwen3.5:9b`

3. **記憶體不足**
   ```
   ❌ SOAP 生成失敗: CUDA out of memory
   ```
   **解決方案：** 使用較小模型或減少 `max_tokens` 參數

### 除錯模式

```bash
# 啟用詳細日誌
uv run python src/cli.py --verbose

# 查看日誌檔案
tail -f /tmp/soapvoice_cli.log
```

## 與 API 整合

CLI 工具使用與 Web API 相同的核心模組，確保一致性：

```python
# Python 程式碼整合範例
from src.cli import SoapVoiceCLI, SOAPConfig

config = SOAPConfig(model_id="qwen3.5:9b")
cli = SoapVoiceCLI(config)
cli.initialize()

result = cli.process_transcript(
    "病人胸悶兩天呼吸困難",
    {"age": "45", "gender": "M"}
)

print(result["subjective"])
```

## 效能優化

### 模型選擇建議

| 模型 | VRAM 需求 | 推理速度 | 品質 | 使用場景 |
|------|-----------|----------|------|----------|
| `qwen3.5:9b` | ~10GB | ⚡ 快速 | 👍 良好 | 日常使用、快速生成 |
| `qwen3.5:27b` | ~20GB | 🐢 中等 | 👍👍 優秀 | 複雜病例、高品質要求 |
| `glm-4.7-flash` | ~8GB | ⚡⚡ 極快 | 👍 良好 | 即時應用、資源有限 |

### 參數調整

```bash
# 調整生成參數（需修改 src/cli.py）
config = SOAPConfig(
    model_id="qwen3.5:9b",
    max_tokens=1024,      # 增加輸出長度
    temperature=0.1,      # 降低隨機性
    num_ctx=8192          # 增加上下文長度
)
```

## 版本資訊

- **v1.0.0** (2026-03-19): 初始版本，支援互動式 CLI
- **功能**: 術語標準化、SOAP 生成、多模型支援、視覺化輸出

## 相關資源

- [AGENTS.md](../AGENTS.md) - 開發指南
- [API_INTEGRATION.md](./API_INTEGRATION.md) - API 整合文件
- [PERFORMANCE_OPTIMIZATION.md](./PERFORMANCE_OPTIMIZATION.md) - 效能優化指南