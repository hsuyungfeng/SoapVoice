# NotebookLM 整合指南

## 概述

CliVoice CLI 現在整合了 NotebookLM 的深度搜尋功能，可以增強醫療資料庫的查詢能力。這個整合讓系統能夠：

- 透過 NotebookLM 搜尋相關的醫學文獻和資料
- 獲取最新的治療指引和臨床建議
- 增強診斷資訊（流行病學、臨床特徵、診斷標準等）
- 取得藥物治療的詳細建議

## 安裝 NotebookLM MCP CLI

### 方法 1: 使用 pip 安裝

```bash
pip install notebooklm-mcp-cli
```

### 方法 2: 從原始碼安裝

```bash
git clone https://github.com/yourusername/notebooklm-mcp-cli.git
cd notebooklm-mcp-cli
pip install -e .
```

### 方法 3: 使用 Docker

```bash
docker pull notebooklm-mcp-cli
docker run -it notebooklm-mcp-cli --help
```

## 設定

### 環境變數

```bash
# 設定 NotebookLM CLI 路徑（如果不在 PATH 中）
export NOTEBOOKLM_CLI_PATH=/path/to/notebooklm-mcp-cli

# 設定快取目錄
export NOTEBOOKLM_CACHE_DIR=~/.cache/clivoice/notebooklm
```

### Python 程式設定

```python
from cli_anything.clivoice.adapters.notebooklm_adapter import NotebookLMAdapter

adapter = NotebookLMAdapter(config={
    "notebooklm_cli_path": "notebooklm-mcp-cli",  # CLI 路徑
    "default_sources": ["icd10", "medical_orders", "atc_drugs"],  # 預設資料來源
    "cache_enabled": True,  # 啟用快取
    "cache_dir": "~/.cache/clivoice/notebooklm"  # 快取目錄
})
```

## 使用範例

### 基本搜尋

```python
from cli_anything.clivoice.adapters.notebooklm_adapter import NotebookLMAdapter

adapter = NotebookLMAdapter()

# 搜尋症狀相關診斷
symptoms = "咳嗽、發燒、喉嚨痛"
diagnoses = adapter.search_symptoms(symptoms, max_results=5)

for diagnosis in diagnoses:
    print(f"診斷: {diagnosis['content']}")
    print(f"信心分數: {diagnosis['confidence']:.2f}")
```

### 治療方案搜尋

```python
# 搜尋特定診斷的治療方案
diagnosis = "急性上呼吸道感染 (J06.9)"
treatments = adapter.search_treatment_protocols(diagnosis, max_results=5)

for treatment in treatments:
    print(f"治療方案: {treatment['content']}")
```

### 藥物建議搜尋

```python
# 搜尋藥物建議
drugs = adapter.search_drug_recommendations("J06.9", max_results=5)

for drug in drugs:
    print(f"藥物: {drug['content']}")
```

### 增強診斷資訊

```python
# 增強流感診斷資訊
enhanced = adapter.enhance_diagnosis("J11.1", "流感")

print(f"流行病學: {enhanced['enhanced_info']['epidemiology']}")
print(f"臨床特徵: {enhanced['enhanced_info']['clinical_features']}")
print(f"診斷標準: {enhanced['enhanced_info']['diagnostic_criteria']}")
print(f"預後: {enhanced['enhanced_info']['prognosis']}")
print(f"整體信心分數: {enhanced['confidence']:.2f}")
```

### 完整臨床工作流程

```python
from cli_anything.clivoice.adapters.notebooklm_adapter import NotebookLMAdapter

adapter = NotebookLMAdapter()

# 病人症狀
symptoms = "咳嗽、發燒 38.5 度、全身酸痛、喉嚨痛"

# Step 1: 搜尋可能的診斷
diagnoses = adapter.search_symptoms(symptoms, max_results=3)

# Step 2: 對每個診斷搜尋治療方案
for diagnosis in diagnoses:
    treatments = adapter.search_treatment_protocols(diagnosis['content'])
    drugs = adapter.search_drug_recommendations(diagnosis['content'])
    enhanced = adapter.enhance_diagnosis(
        diagnosis['content'].split('(')[-1].rstrip(')'),  # 提取 ICD 代碼
        diagnosis['content'].split('(')[0].strip()  # 提取診斷名稱
    )
```

## CLI 使用方式

### 執行範例腳本

```bash
# 安裝 cli-anything-clivoice
pip install cli-anything-clivoice

# 執行 NotebookLM 範例
python examples/notebooklm_examples.py
```

### Python API 使用

```python
from cli_anything.clivoice.adapters.notebooklm_adapter import NotebookLMAdapter

# 建立適配器
adapter = NotebookLMAdapter()

# 搜尋症狀
result = adapter.search_symptoms("咳嗽", max_results=5)
print(json.dumps(result, ensure_ascii=False, indent=2))
```

## 快取機制

NotebookLM 適配器使用快取來提高效能：

- **快取位置**: `~/.cache/clivoice/notebooklm/`
- **快取鍵值**: MD5 hash of (query + context)
- **快取啟用**: 預設啟用，可透過 `config["cache_enabled"]` 停用

### 手動清除快取

```bash
rm -rf ~/.cache/clivoice/notebooklm/
```

## 錯誤處理

```python
from cli_anything.clivoice.adapters.notebooklm_adapter import NotebookLMAdapter

adapter = NotebookLMAdapter()

try:
    result = adapter.search_symptoms("咳嗽")
except RuntimeError as e:
    if "找不到 NotebookLM CLI" in str(e):
        print("請先安裝 NotebookLM MCP CLI")
    elif "超時" in str(e):
        print("NotebookLM 執行超時，請稍後再試")
    else:
        print(f"其他錯誤: {e}")
```

## API 參考

### NotebookLMAdapter

#### `__init__(config: Optional[Dict[str, Any]] = None)`

初始化 NotebookLM 適配器。

**參數**:
- `config`: 設定字典，包含：
  - `notebooklm_cli_path`: NotebookLM CLI 路徑
  - `default_sources`: 預設資料來源列表
  - `cache_enabled`: 是否啟用快取
  - `cache_dir`: 快取目錄路徑

#### `search_medical_database(query: NotebookLMQuery) -> MedicalSearchResult`

搜尋醫療資料庫。

#### `search_symptoms(symptoms: str, max_results: int = 10) -> List[Dict]`

搜尋症狀相關的診斷建議。

#### `search_treatment_protocols(diagnosis: str, max_results: int = 10) -> List[Dict]`

搜尋特定診斷的治療方案。

#### `search_drug_recommendations(diagnosis: str, max_results: int = 10) -> List[Dict]`

搜尋特定診斷的藥物建議。

#### `enhance_diagnosis(diagnosis_code: str, diagnosis_name: str) -> Dict`

增強診斷資訊。

### NotebookLMQuery

```python
@dataclass
class NotebookLMQuery:
    query: str                    # 查詢文字
    context: Optional[str] = None # 上下文
    sources: Optional[List[str]] = None  # 資料來源
    max_results: int = 10         # 最大結果數
    include_citations: bool = True  # 包含引用
    language: str = "zh-tw"      # 語言
```

### MedicalSearchResult

```python
@dataclass
class MedicalSearchResult:
    query: str                          # 原始查詢
    diagnosis_suggestions: List[Dict]   # 診斷建議
    treatment_protocols: List[Dict]      # 治療方案
    drug_recommendations: List[Dict]    # 藥物建議
    evidence_summary: str                 # 證據摘要
    confidence_scores: Dict[str, float]  # 信心分數
    sources: List[Dict]                  # 來源列表
```

## 常見問題

### Q: NotebookLM MCP CLI 未安裝怎麼辦？

**A**: 請參考上面的「安裝 NotebookLM MCP CLI」章節進行安裝。

### Q: 搜尋結果為空怎麼辦？

**A**: 
1. 確認 NotebookLM MCP CLI 已正確設定
2. 嘗試增加 `max_results` 參數
3. 檢查網路連線
4. 查看日誌了解更多錯誤資訊

### Q: 如何停用快取？

**A**: 
```python
adapter = NotebookLMAdapter(config={"cache_enabled": False})
```

### Q: 快取佔用太多空間怎麼辦？

**A**: 手動刪除快取目錄：
```bash
rm -rf ~/.cache/clivoice/notebooklm/
```

## 整合架構

```
┌─────────────────────────────────────────┐
│         CliVoice CLI                   │
├─────────────────────────────────────────┤
│  NotebookLMAdapter                      │
│  ├── search_medical_database()         │
│  ├── search_symptoms()                 │
│  ├── search_treatment_protocols()       │
│  ├── search_drug_recommendations()      │
│  └── enhance_diagnosis()               │
├─────────────────────────────────────────┤
│  NotebookLM MCP CLI                     │
│  ├── search command                    │
│  ├── query processing                   │
│  └── result formatting                 │
├─────────────────────────────────────────┤
│  外部資料來源                            │
│  ├── ICD-10 疾病分類                   │
│  ├── 醫療服務支付標準                  │
│  ├── ATC 藥物分類                      │
│  └── 醫學文獻資料庫                    │
└─────────────────────────────────────────┘
```

## 授權

本整合模組遵循 MIT License。

## 聯絡方式

- GitHub Issues: https://github.com/yourusername/clivoice-cli-harness/issues
- 文件: https://github.com/yourusername/clivoice-cli-harness/wiki
