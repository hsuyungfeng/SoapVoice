## SoapVoice 一鍵離線版

## 簡介

 SoapVoice 離線版本包含完整功能，無需安裝 Ollama，直接執行！

### 內建元件

| 元件 | 說明 | 大小 |
|------|------|------|
| FastAPI 伺服器 | Web API + 前端網頁 | - |
| llama.cpp | LLM 推理引擎 | 含於套件 |
| Qwen2.5:7b GGUF | AI 模型 | ~4.5GB |
| faster-whisper-small | 語音轉文字 | ~464MB |
| medical.db | 醫療資料庫 (ICD-10, 藥品) | ~70MB |
| case_templates.db | 病例範本資料庫 (RAG) | ~7MB |

## 總大小

**約 5.5GB**（包含所有模型 + 資料庫）

## 使用方式

### 方式一：直接執行 (Python)

```bash
# 安裝依賴
uv sync

# 啟動離線伺服器
uv run python src/offline_server.py
```

### 方式二：打包為 EXE (Windows)

```bash
# 建置
pyinstaller SoapVoice.spec --clean

# 執行
dist/SoapVoice/SoapVoice.exe
```

## 開啟瀏覽器

執行後開啟 `http://localhost:8000`

## 模型選擇

| 模型 | 大小 | 速度 | 推薦 |
|------|------|------|------|
| Qwen2.5:7b Q4_K_M | 4.5GB | ~10s | ⭐ 最佳 |
| Qwen2.5:3b Q4_K_M | 2.0GB | ~15s | 輕量 |

## 常見問題

### Q: 首次執行需要網路嗎？
A: 不需要！所有模型和資料庫已內建。

### Q: EXE 檔案多大？
A: 預計 3-5GB（取決於壓縮效果）

### Q: 需要什麼系統需求？
A: Windows 10/11 + 8GB RAM