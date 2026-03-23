# cli-anything-clivoice

醫療診斷輔助系統 CLI harness - 整合 ICD10v2, medicalordertreeview, ATCcodeTW 三個子系統，在 SOAP 病歷生成後自動找到正確的診斷、醫療醫囑和藥物。

## 功能特色

### 🏥 整合三大醫療系統
- **ICD10v2**: 疾病診斷分類系統 (96,802 個診斷代碼)
- **medicalordertreeview**: 醫療服務給付項目系統 (42,776 個給付項目)
- **ATCcodeTW**: 藥物分類系統 (台灣 ATC 藥物分類)

### 🔄 智慧診斷流程
1. **SOAP 病歷分析**: 解析 SOAP 格式病歷，提取症狀關鍵字
2. **診斷匹配**: 使用 ICD10v2 匹配症狀與診斷代碼
3. **醫囑生成**: 根據診斷查詢醫療給付標準
4. **藥物推薦**: 推薦合適的 ATC 分類藥物

### 🎯 核心功能
- **互動式 CLI**: 支援命令列互動與批次處理
- **多格式輸出**: JSON、文字、表格、Markdown
- **智慧推薦**: 基於症狀、患者條件、藥物交互作用
- **批次處理**: 支援多個 SOAP 病歷批次分析
- **API 整合**: 與現有醫療系統無縫整合

## 快速開始

### 安裝

```bash
# 從 PyPI 安裝
pip install cli-anything-clivoice

# 或從原始碼安裝
git clone https://github.com/soapvoice/clivoice.git
cd clivoice
pip install -e .
```

### 基本使用

```bash
# 顯示幫助
clivoice --help

# 互動式診斷
clivoice diagnose interactive

# 從 SOAP 檔案分析
clivoice diagnose from-soap --file soap.json

# 完整診斷流程
clivoice integrate full-pipeline --soap-file patient.json --output report.json
```

## 使用範例

### 範例 1: 互動式診斷
```bash
$ clivoice diagnose interactive

🔍 醫療診斷輔助系統
========================
請輸入患者症狀 (輸入空行結束):
> 病人胸悶兩天呼吸困難
> 有輕微咳嗽，無發燒
> 

請輸入患者資訊:
年齡: 45
性別: M
過敏史: penicillin

📋 診斷結果:
• J20.9 - 急性支氣管炎 (信心度: 85%)
• R07.89 - 其他胸痛 (信心度: 72%)

💊 推薦醫囑:
• 32001B - 支氣管擴張劑吸入治療
• 01001 - 門診診察費

💊 推薦藥物:
• R03AC - Salbutamol (沙丁胺醇)
• R05CB - Dextromethorphan (右美沙芬)
```

### 範例 2: 批次處理
```bash
# 處理目錄中所有 SOAP 檔案
clivoice integrate batch \
  --input-dir ./soaps \
  --output-dir ./reports \
  --format json

# 產生摘要報告
clivoice integrate summary --input-dir ./reports
```

### 範例 3: API 模式
```bash
# JSON 輸出 (適合程式處理)
clivoice diagnose from-soap --file soap.json --format json

# 輸出範例:
{
  "diagnoses": [
    {
      "icd10_code": "J20.9",
      "name": "急性支氣管炎",
      "confidence": 0.85,
      "symptoms": ["胸悶", "呼吸困難", "咳嗽"]
    }
  ],
  "medical_orders": [...],
  "drug_recommendations": [...]
}
```

## 命令參考

### 診斷命令
```bash
# 從 SOAP 病歷分析診斷
clivoice diagnose from-soap --file <file> [--format json|text|table]

# 互動式診斷
clivoice diagnose interactive

# 搜尋 ICD-10 診斷代碼
clivoice diagnose search --query "支氣管炎" [--limit 10]

# 匹配症狀與診斷
clivoice diagnose match --symptoms "胸悶,呼吸困難" --age 45
```

### 醫囑命令
```bash
# 根據診斷生成醫囑
clivoice order generate --diagnosis J20.9 [--type outpatient|inpatient]

# 搜尋醫療給付項目
clivoice order search --query "支氣管擴張劑" [--category respiratory]

# 驗證醫囑合規性
clivoice order validate --orders orders.json [--patient patient.json]
```

### 藥物命令
```bash
# 推薦藥物
clivoice drug recommend --diagnosis J20.9 [--patient-age 45]

# 搜尋藥物
clivoice drug search --query "Salbutamol" [--atc-category R03]

# 檢查藥物交互作用
clivoice drug check-interactions --drugs "drug1,drug2,drug3"
```

### 整合命令
```bash
# 完整診斷流程
clivoice integrate full-pipeline --soap-file <file> [--output <file>]

# 批次處理
clivoice integrate batch --input-dir <dir> --output-dir <dir>

# 產生摘要報告
clivoice integrate summary --input-dir <dir> [--format html|pdf|markdown]
```

## 配置設定

### 環境變數
```bash
# ICD10v2 資料路徑
export ICD10_DATA_PATH=/path/to/icd10-data.js

# medicalordertreeview API
export MEDICAL_ORDER_API_URL=http://localhost:5000
export MEDICAL_ORDER_API_KEY=your_api_key

# ATCcodeTW API
export ATC_DRUG_API_URL=http://localhost:5001
export ATC_DRUG_API_KEY=your_api_key

# 快取設定
export CACHE_ENABLED=true
export CACHE_TTL_SECONDS=3600
```

### 配置文件
建立 `~/.clivoice/config.yaml`:
```yaml
icd10:
  data_path: ./data/icd10-data.js
  search_threshold: 0.7

medical_order:
  api_url: http://localhost:5000
  api_key: ${MEDICAL_ORDER_API_KEY}
  timeout_seconds: 30

atc_drug:
  api_url: http://localhost:5001
  api_key: ${ATC_DRUG_API_KEY}
  timeout_seconds: 30

cache:
  enabled: true
  ttl_seconds: 3600
  max_size_mb: 100

logging:
  level: INFO
  file: ~/.clivoice/logs/clivoice.log
```

## 開發指南

### 專案結構
```
cli_anything/clivoice/
├── core/                    # 核心引擎
│   ├── diagnosis_engine.py    # 診斷引擎
│   ├── order_generator.py     # 醫囑生成器
│   ├── drug_recommender.py    # 藥物推薦器
│   └── integration_orchestrator.py  # 整合協調器
├── adapters/                # 子系統適配器
│   ├── icd10_adapter.py       # ICD10v2 適配器
│   ├── medical_order_adapter.py  # medicalordertreeview 適配器
│   └── atc_drug_adapter.py    # ATCcodeTW 適配器
├── models/                  # 資料模型
│   ├── patient.py             # 病患模型
│   ├── diagnosis.py           # 診斷模型
│   ├── medical_order.py       # 醫囑模型
│   └── drug_recommendation.py # 藥物推薦模型
├── utils/                   # 工具函數
│   ├── file_utils.py          # 檔案工具
│   ├── validation.py          # 驗證工具
│   └── logging_config.py      # 日誌配置
├── cli/                     # CLI 介面
│   ├── commands.py            # CLI 命令定義
│   └── clivoice_cli.py        # CLI 主入口
└── tests/                   # 測試檔案
    ├── test_core.py           # 核心功能測試
    └── test_full_e2e.py       # 端到端測試
```

### 開發環境設定
```bash
# 克隆專案
git clone https://github.com/soapvoice/clivoice.git
cd clivoice

# 建立虛擬環境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安裝開發依賴
pip install -e ".[dev]"

# 執行測試
pytest tests/ -v

# 程式碼檢查
ruff check .
black .
mypy .
```

### 新增功能
1. **新增診斷規則**: 編輯 `core/diagnosis_engine.py`
2. **新增醫囑模板**: 編輯 `core/order_generator.py`
3. **新增藥物規則**: 編輯 `core/drug_recommender.py`
4. **新增 CLI 命令**: 編輯 `cli/commands.py`

## API 參考

### Python API
```python
from cli_anything.clivoice.core import DiagnosisEngine, OrderGenerator, DrugRecommender
from cli_anything.clivoice.models import Patient, SOAPNote

# 初始化引擎
engine = DiagnosisEngine()
order_gen = OrderGenerator()
drug_rec = DrugRecommender()

# 分析 SOAP 病歷
soap = SOAPNote.from_file("patient.json")
diagnoses = engine.analyze(soap)

# 生成醫囑
orders = order_gen.generate(diagnoses[0])

# 推薦藥物
drugs = drug_rec.recommend(diagnoses[0], patient)
```

### REST API (可選)
```bash
# 啟動 API 伺服器
clivoice api start --port 8080

# API 端點
POST /api/v1/diagnose    # 診斷分析
POST /api/v1/orders      # 醫囑生成
POST /api/v1/drugs       # 藥物推薦
GET  /api/v1/health      # 健康檢查
```

## 故障排除

### 常見問題

**Q: 無法連接子系統 API**
```bash
# 檢查服務狀態
curl http://localhost:5000/api/v1/health
curl http://localhost:5001/api/v1/health

# 檢查環境變數
echo $MEDICAL_ORDER_API_URL
echo $ATC_DRUG_API_URL
```

**Q: ICD-10 資料載入失敗**
```bash
# 檢查檔案路徑
ls -la $ICD10_DATA_PATH

# 重新下載資料
clivoice data download --type icd10
```

**Q: 記憶體使用過高**
```bash
# 啟用快取
export CACHE_ENABLED=true

# 限制批次大小
clivoice integrate batch --batch-size 10

# 清理快取
clivoice cache clear
```

### 除錯模式
```bash
# 啟用詳細日誌
export LOG_LEVEL=DEBUG
clivoice diagnose from-soap --file soap.json --verbose

# 輸出日誌到檔案
clivoice --log-file debug.log diagnose from-soap --file soap.json
```

## 貢獻指南

### 提交問題
1. 檢查是否已有相關問題
2. 提供重現步驟和錯誤訊息
3. 包含環境資訊 (OS, Python 版本等)

### 提交程式碼
1. Fork 專案
2. 建立功能分支
3. 撰寫測試
4. 確保通過所有測試
5. 提交 Pull Request

### 程式碼風格
- 遵循 PEP 8 規範
- 使用型別提示
- 撰寫文件字串
- 添加單元測試

## 授權

本專案採用 MIT 授權 - 詳見 [LICENSE](LICENSE) 檔案。

## 支援

- 📖 [文件](https://github.com/soapvoice/clivoice/wiki)
- 🐛 [問題回報](https://github.com/soapvoice/clivoice/issues)
- 💬 [討論區](https://github.com/soapvoice/clivoice/discussions)
- 📧 聯絡: team@soapvoice.example.com

## 相關專案

- [SoapVoice](https://github.com/soapvoice/soapvoice) - 醫療語音轉 SOAP 病歷系統
- [ICD10v2](https://github.com/soapvoice/icd10v2) - ICD-10 診斷代碼導航系統
- [medicalordertreeview](https://github.com/soapvoice/medicalordertreeview) - 醫療服務給付項目系統
- [ATCcodeTW](https://github.com/soapvoice/atccodetw) - 台灣 ATC 藥物分類系統