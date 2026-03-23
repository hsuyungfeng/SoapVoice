# CliVoice CLI Harness

醫療語音轉 SOAP 病歷系統的 CLI 介面，整合三個醫療子系統：
1. ICD10v2 — 疾病診斷代碼系統
2. medicalordertreeview — 醫療服務支付標準系統  
3. ATCcodeTW — 台灣 ATC 藥物分類系統

## 快速開始

### 安裝

```bash
# 克隆專案
git clone <repository-url>
cd agent-harness

# 建立虛擬環境
python3 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install -e .
```

### 基本使用

```bash
# 顯示幫助
clivoice --help

# 分析 SOAP 病歷
clivoice analyze "病人咳嗽發燒三天" --json

# 根據症狀查詢診斷
clivoice diagnose 咳嗽 --limit 5

# 進入互動模式
clivoice repl
```

## 功能特色

### 完整醫療流程整合
```
SOAP 病歷 → 症狀提取 → ICD10v2 診斷 → medicalordertreeview 醫囑 → ATCcodeTW 藥物
```

### CLI 命令

| 命令 | 說明 | 範例 |
|------|------|------|
| `analyze` | 分析 SOAP 病歷 | `clivoice analyze "病人咳嗽發燒" --json` |
| `diagnose` | 症狀查詢診斷 | `clivoice diagnose 咳嗽 --limit 5` |
| `orders` | 診斷查詢醫囑 | `clivoice orders J06.9 --category 藥物` |
| `drugs` | 診斷查詢藥物 | `clivoice drugs J06.9 --atc-class N02` |
| `batch-process` | 批次處理 | `clivoice batch-process soap_notes.txt` |
| `repl` | 互動模式 | `clivoice repl` |

### 輸出格式
- **文字格式** (預設): 人類可讀的格式化輸出
- **JSON 格式** (`--json`): 機器可讀的結構化資料
- **Markdown 格式**: 適合文件報告

## 系統架構

```
agent-harness/
├── cli_anything/clivoice/
│   ├── models/          # 資料模型
│   ├── core/           # 核心引擎
│   ├── adapters/       # 系統適配器
│   ├── cli/           # CLI 介面
│   ├── tests/         # 測試檔案
│   ├── __init__.py
│   └── __main__.py
├── setup.py           # 套件配置
├── requirements.txt   # 依賴套件
├── TEST.md           # 測試文件
├── CLIVOICE.md       # 系統設計
└── example_usage.py  # 使用範例
```

## 使用範例

### 範例 1: 基本分析

```bash
clivoice analyze "病人主訴咳嗽、發燒三天，喉嚨痛。體溫38.5°C，喉嚨紅腫。診斷為急性上呼吸道感染。建議給予退燒藥，休息多喝水。" --verbose
```

### 範例 2: JSON 輸出

```bash
clivoice analyze "胃痛、噁心、食慾不振" --json --output result.json
```

### 範例 3: 批次處理

```bash
# 建立測試檔案
echo "病人咳嗽發燒" > soap_notes.txt
echo "胃痛噁心" >> soap_notes.txt

# 批次處理
clivoice batch-process soap_notes.txt --output batch_results.json
```

### 範例 4: Python API 使用

```python
from cli_anything.clivoice import IntegrationOrchestrator, SOAPNote

# 建立 SOAP 病歷
soap_note = SOAPNote.from_text("""
主觀資料(S): 病人主訴咳嗽、發燒
客觀資料(O): 體溫38.5°C
評估(A): 急性上呼吸道感染
計畫(P): 給予退燒藥
""")

# 處理病歷
orchestrator = IntegrationOrchestrator()
result = orchestrator.process_soap_note(soap_note)

print(f"診斷: {result.diagnoses[0].name if result.diagnoses else '無'}")
print(f"醫囑: {len(result.orders)} 個")
print(f"藥物: {len(result.drug_recommendations)} 種")
```

## 測試

```bash
# 執行所有測試
python -m pytest cli_anything/clivoice/tests/ -v

# 執行特定測試
python -m pytest cli_anything/clivoice/tests/test_models.py -v

# 產生覆蓋率報告
python -m pytest cli_anything/clivoice/tests/ --cov=cli_anything.clivoice --cov-report=html
```

## 開發

### 依賴管理

```bash
# 安裝開發依賴
pip install -e ".[dev]"

# 格式化程式碼
black cli_anything/clivoice/

# Lint 檢查
ruff check cli_anything/clivoice/
```

### 新增功能

1. 在 `models/` 新增資料模型
2. 在 `core/` 新增業務邏輯
3. 在 `adapters/` 新增系統整合
4. 在 `cli/` 新增 CLI 命令
5. 在 `tests/` 新增對應測試

## 授權

MIT License

## 貢獻

歡迎提交 Issue 和 Pull Request！

## 聯絡方式

- 問題回報: GitHub Issues
- 功能建議: GitHub Discussions