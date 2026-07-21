# AGENTS.md — SoapVoice 開發指南

> 醫療語音轉 SOAP 病歷系統（Medical Voice-to-SOAP Conversion System）
> Python 3.11+ · FastAPI · **Gemma 4:E4B (llama-cpp-python)** · Faster-Whisper · uv 套件管理
> **Windows CPU 全離線版** — 無需 GPU，無需雲端 API

## 系統 Pipeline

```
語音輸入 → [ASR 引擎] → 術語標準化 → ICD-10 對應 → Gemma 4:E4B (llama.cpp) → SOAP 病歷
    ↓                         ↑
Faster-Whisper medium    Tesseract OCR / Ollama Vision (備援)
(本地離線 CPU)           (HIS 畫面患者資訊擷取)
          ↓
    Desktop GUI 側邊欄 (ttkbootstrap Superhero) 右貼螢幕
```

目標：Windows CPU 完全離線，右側邊欄 GUI，零延遲 SOAP 生成。

---

## 建置與執行指令

```bash
# 安裝依賴（使用 uv，非 pip）
uv sync                        # 生產依賴
uv sync --group dev            # 含開發工具（pytest, ruff, black, locust）

# 啟動 API 伺服器（須先確認 Ollama 運行中：ollama serve）
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## 測試指令

```bash
uv run pytest tests/ -v                                                          # 所有測試
uv run pytest tests/test_nlp.py -v                                               # 單一檔案
uv run pytest tests/test_nlp.py::TestMedicalTerminologyMapper::test_map_term_direct -v  # 單一函式
uv run pytest tests/ --cov=src --cov-report=html --cov-report=term               # 含覆蓋率
uv run pytest tests/test_nlp.py tests/test_soap.py tests/test_init.py -v         # 快速測試（不需模型）
```

## 程式碼品質工具

```bash
uv run ruff check src/ tests/           # Lint 檢查
uv run ruff check src/ tests/ --fix     # 自動修復
uv run black src/ tests/                # 格式化
uv run black --check src/ tests/        # 格式化檢查（不修改）
```

---

## 專案結構

```
src/
├── main.py                    # FastAPI 入口（app 實例、lifespan、路由註冊）
├── api/
│   ├── rest.py                # REST 端點（/clinical/normalize, /icd10, /soap/generate）
│   └── websocket.py           # WebSocket 端點（即時語音串流轉錄）
├── asr/
│   ├── whisper_model.py       # Faster-Whisper ASR 包裝（CPU 優化，medium 模型）
│   ├── qwen3asr_model.py      # Qwen3-ASR 包裝（備用）
│   ├── asr_factory.py         # ASR 引擎工廠 + ChineseConverter（opencc 簡→繁）
│   ├── stream_transcriber.py  # 串流轉錄邏輯
│   └── vocabulary.py          # 醫療詞彙表
├── nlp/
│   ├── terminology_mapper.py  # 口語中文→標準醫療英文（80+ 術語映射）
│   ├── icd10_classifier.py    # 症狀→ICD-10 代碼映射（50+ 症狀）
│   ├── soap_classifier.py     # 關鍵字規則 S/O/A/P 分類
│   └── ocr_parser.py          # HIS 畫面截圖 OCR（Tesseract 主力 + Ollama Vision 備援）
├── soap/
│   └── soap_generator.py      # LLM SOAP 病歷生成（整合術語標準化 + ICD-10）
├── llm/
│   ├── ollama_engine.py       # Ollama API 推理引擎
│   └── llama_engine.py        # llama-cpp-python 推理引擎（Windows 離線主力）
├── gui/
│   ├── desktop_app.py         # 桌面側邊欄 GUI（ttkbootstrap Superhero 主題，右貼螢幕）
│   └── config_manager.py      # GUI 設定管理
├── db/                      # 資料庫
│   ├── local_database.py    # 查詢介面（含 ICD-10 + 疾病知識圖譜）
│   └── llm_db_cli.py        # LLM 資料庫 CLI
├── phase8/
│   └── capture_ocr.py         # 截圖 + OCR 整合（Tesseract 主力，EasyOCR 備援）
├── security/
│   └── auth.py                # API Key + JWT 認證模組
├── scripts/                    # 工具腳本
│   └── import_kg_data.py      # 疾病知識圖譜 ETL（簡轉繁 + SQLite 匯入）
└── data/
    ├── local_db/medical.db    # 本地醫療資料庫
    └── kg_import/             # 知識圖譜原始 JSON 資料
```

---

## 程式碼風格與規範

### 格式化設定

- **行寬上限：** 100 字元（black + ruff 皆設定 100）
- **Python 版本：** 3.11+（target-version = "py311"）
- **格式化工具：** black（主）+ ruff（lint），**引號風格：** 雙引號

### 匯入順序（ruff/isort 規則，三段空行分隔）

```python
# 1. 標準庫
import os
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass
# 2. 第三方套件
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
# 3. 專案內部模組（一律使用絕對路徑 src.xxx，不使用相對匯入）
from src.nlp.terminology_mapper import MedicalTerminologyMapper, TermMapping
```

### 型別標註

- 所有公開函式必須有型別標註（參數 + 回傳值）
- 使用 `typing` 模組：`Optional`, `Dict`, `List`, `Any`, `Tuple`
- 資料結構：`@dataclass`（NLP/ASR 內部）或 `pydantic.BaseModel`（API 層）

### 命名規範

| 類型 | 規範 | 範例 |
|------|------|------|
| 類別 | PascalCase | `MedicalTerminologyMapper`, `SOAPGenerator` |
| 函式/方法 | snake_case | `map_term()`, `generate_soap()` |
| 常數 | UPPER_SNAKE | `SOAP_KEYWORDS`, `CHINESE_TO_ENGLISH` |
| 私有方法 | _前綴 | `_build_prompt()`, `_parse_response()` |
| 模組檔案 | snake_case | `terminology_mapper.py` |
| 測試檔案/類別 | test_ / Test前綴 | `test_nlp.py`, `TestMedicalTerminologyMapper` |

### 文件字串（Docstring）

- 模組層級三引號描述功能（繁體中文），類別與公開方法用 Google 風格
- **繁體中文為主要文件語言**（docstring、註解、commit 訊息皆用繁體中文）

```python
"""醫療術語標準化模組 — 提供口語中文轉專業醫療英文術語的映射功能"""

class SOAPGenerator:
    """SOAP 病歷生成器"""
    def generate(self, transcript: str) -> Dict[str, Any]:
        """生成 SOAP 病歷
        Args:
            transcript: 醫療對話轉錄文字
        Returns:
            包含 soap、metadata 等欄位的字典
        """
```

### 錯誤處理

- LLM/ASR 呼叫包入 `try/except`，失敗時 fallback（如使用原始文字）
- API 端點使用 `HTTPException` 回傳適當狀態碼
- 所有模組使用 `logging`（`logger = logging.getLogger(__name__)`）

```python
try:
    normalized_text, mappings = self._mapper.map_text(transcript)
except Exception as e:
    logger.warning(f"術語標準化失敗，使用原始文字: {e}")
    normalized_text = transcript
    mappings = []
```

### 單例模式

全域服務用模組層級延遲初始化；類別內重量級依賴用 `self._xxx` 於 `__init__` 建立一次。

```python
_soap_generator: Optional[SOAPGenerator] = None
def get_soap_generator() -> SOAPGenerator:
    global _soap_generator
    if _soap_generator is None:
        _soap_generator = SOAPGenerator()
    return _soap_generator
```

---

## 測試規範

- 測試框架：pytest + pytest-asyncio，檔案放 `tests/`，檔名 `test_*.py`
- 使用 `@pytest.fixture` 建立可重用測試物件
- 覆蓋率目標：≥80%（`pyproject.toml` 中 `fail_under = 80`）
- `conftest.py` 在專案根目錄，自動將專案根加入 `sys.path`

## 環境變數

主要設定來自 `.env`（由 `python-dotenv` 載入）：

- `CORS_ORIGINS` — 允許的前端來源（預設含 localhost:3000）
- `LLM_MODEL` — LLM 模型名稱（預設 `Qwen/Qwen3-32B-Instruct`）
- `INITIALIZE_LLM` — 是否啟動時初始化 LLM（`true`/`false`）
- `DEV_MODE` — 開發模式啟用 auto-reload
- `JWT_SECRET_KEY` — JWT 簽密鑰

## 重要注意事項

1. **所有文件以繁體中文為主**（docstring、註解、文件皆使用繁體中文）
2. **使用 uv 管理依賴**，不使用 pip install（執行用 `uv run`）
3. **SOAP_KEYWORDS 單一來源**：定義在 `soap_classifier.py`，`soap_generator.py` 引用之
4. **術語標準化已整合至 SOAP 生成流程**：LLM prompt 自動含標準術語 + ICD-10 候選碼
5. **ASR 引擎可切換**：透過 `asr_backend` 參數選擇 whisper 或 qwen3asr
6. **主力 LLM：Gemma 4:E4B**（`llama-cpp-python 0.3.20`），使用 `<start_of_tell>` 控制標記；Ollama 為補充後端
7. **OCR 優先順序**：Tesseract-OCR → Ollama Vision (gemma4:e2b) → 純截圖
8. **GUI 架構：雙階段側邊欄**
   - `ttk.Window` + `superhero` 主題（`ttkbootstrap`）
   - **緊湊模式** `420×240`：控制列（錄音/停止/處理），停靠於螢幕右上角
   - **展開模式** `420×900`：LLM 完成後自動展開，顯示患者卡片與完整 SOAP 病歷
   - 使用 `ttk.Labelframe`（小寫 f）搭配 `bootstyle=` 參數
9. **語音與逐字稿須保存**：每次錄音須儲存原始音檔（WAV/PCM）與 ASR 逐字稿至 `data/recordings/` 目錄
10. **疾病知識圖譜整合**：資料庫已匯入 8,807 疾病知識（症狀/藥品/飲食/檢查/科室/併發症），來源為 baiyang2464/chatbot-base-on-Knowledge-Graph，使用 `scripts/import_kg_data.py` 進行 ETL 與簡轉繁，新增 7 張資料表（disease_info, disease_symptoms, disease_drugs, disease_foods, disease_checks, disease_departments, disease_acompany）

## 資料庫與外部集成 (Database & Integrations)

### A. 獨立本地資料庫 (`data/local_db/medical.db`)
為了確保系統能在完全離線且獨立的環境運行，系統使用 SQLite 資料庫 `medical.db`。該資料庫除了內建的 ICD-10 代碼、藥品與醫囑外，還整合了從 `DrtoolboxLocalServer` 專案中克隆的臨床醫療知識圖譜（含疾病特徵、療程適應症與指引等 9 張關聯表）。

### B. 雙向同步更新機制
當 `DrtoolboxLocalServer` 的知識圖譜或資料結構有所更新時，必須依序執行以下步驟進行資料同步：
1. **更新資料庫表結構**：在 `DrtoolboxLocalServer` 根目錄下執行以下腳本，將最新的臨床圖譜與資訊表複製至 `SoapVoice`：
   ```bash
   python scripts/copy_db_to_soapvoice.py
   ```
2. **同步 ASR 熱詞與詞典**：在 `DrtoolboxLocalServer` 根目錄下執行以下腳本，將圖譜中的所有醫療節點（如專有名詞、症狀等）去重後合併寫入 `SoapVoice/keywords.json`，防止語音聽寫時專用術語辨識錯誤：
   ```bash
   python scripts/export_nodes_to_soapvoice_keywords.py
   ```

### C. 臨床用藥與處置合規判定 (Clinical Compliance Guard)
* 系統的 SOAP 病歷生成模組在輸出 Assessment & Plan 時，會透過 `ComplianceGuard` 比對診斷與計畫。
* 任何可能發生的食物/用藥安全排斥、過敏禁忌皆會自 `medical.db` 中的知識庫表進行推導，並即時產出合規警告資訊。



## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
