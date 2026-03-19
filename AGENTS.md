# AGENTS.md — SoapVoice 開發指南

> 醫療語音轉 SOAP 病歷系統（Medical Voice-to-SOAP Conversion System）
> Python 3.11+ · FastAPI · Ollama/Qwen3.5 · Faster-Whisper · uv 套件管理

## 系統 Pipeline

```
語音輸入 → [可選 ASR 引擎] → 術語標準化 → ICD-10 對應 → Qwen3.5 LLM → SOAP 病歷
                ↓
        Faster-Whisper (繁體) 或 Qwen3-ASR (簡體→繁體)
```

目標：加入 CLI 互動介面，並支援以較小模型生成 SOAP 病歷記錄。

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
│   ├── whisper_model.py       # Faster-Whisper ASR 包裝
│   ├── qwen3asr_model.py      # Qwen3-ASR 包裝
│   ├── asr_factory.py         # ASR 引擎工廠 + ChineseConverter（opencc 簡→繁）
│   ├── stream_transcriber.py  # 串流轉錄邏輯
│   └── vocabulary.py          # 醫療詞彙表
├── nlp/
│   ├── terminology_mapper.py  # 口語中文→標準醫療英文（80+ 術語映射）
│   ├── icd10_classifier.py    # 症狀→ICD-10 代碼映射（50+ 症狀）
│   └── soap_classifier.py     # 關鍵字規則 S/O/A/P 分類
├── soap/
│   └── soap_generator.py      # LLM SOAP 病歷生成（整合術語標準化 + ICD-10）
├── llm/
│   ├── ollama_engine.py       # Ollama API 推理引擎（主要使用）
│   └── vllm_engine.py         # vLLM 推理引擎（備用）
└── security/
    └── auth.py                # API Key + JWT 認證模組
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
6. **Ollama 為主要 LLM 後端**（非 vLLM），模型：qwen3.5:9b（主力）/ qwen3.5:27b（備用）
7. **語音與逐字稿須保存**：每次錄音須儲存原始音檔（WAV/PCM）與 ASR 逐字稿至 `data/recordings/` 目錄
