# CliVoice - 醫療診斷輔助系統 CLI Harness

## 系統概述

CliVoice 是一個整合三個醫療子系統的 CLI harness，用於在 SOAP 病歷生成後，自動找到正確的診斷、醫療醫囑和藥物。

### 整合的三個子系統

1. **ICD10v2** - 疾病診斷分類系統
   - 功能：ICD-10 診斷代碼查詢與匹配
   - 資料：96,802 個 ICD-10 診斷代碼
   - 格式：純前端 JavaScript 應用

2. **medicalordertreeview** - 醫療服務給付項目系統
   - 功能：台灣健保給付標準查詢
   - 資料：42,776 個醫療服務給付項目
   - 格式：FastAPI 後端 + 前端

3. **ATCcodeTW** - 藥物分類系統
   - 功能：台灣 ATC 藥物分類查詢
   - 資料：診所藥物庫與 ATC 分類
   - 格式：Flask 後端 + 前端

## 系統架構

### 資料流
```
SOAP 病歷輸入
    ↓
[診斷分析模組] → ICD10v2 (疾病診斷)
    ↓
[醫囑生成模組] → medicalordertreeview (醫療給付項目)
    ↓
[藥物推薦模組] → ATCcodeTW (藥物分類)
    ↓
整合輸出：診斷 + 醫囑 + 藥物
```

### 核心功能

1. **診斷匹配**
   - 從 SOAP 病歷提取症狀關鍵字
   - 查詢 ICD10v2 資料庫
   - 返回匹配的診斷代碼與名稱

2. **醫囑生成**
   - 根據診斷結果
   - 查詢 medicalordertreeview 給付標準
   - 生成適當的醫療醫囑項目

3. **藥物推薦**
   - 根據診斷和醫囑
   - 查詢 ATCcodeTW 藥物庫
   - 推薦合適的藥物

## CLI 命令設計

### 命令群組

```
clivoice
├── diagnose      # 診斷相關命令
│   ├── from-soap    # 從 SOAP 病歷分析診斷
│   ├── search       # 搜尋 ICD-10 診斷代碼
│   └── match        # 匹配症狀與診斷
├── order         # 醫囑相關命令
│   ├── generate     # 生成醫療醫囑
│   ├── search       # 搜尋給付項目
│   └── validate     # 驗證醫囑合規性
├── drug          # 藥物相關命令
│   ├── recommend    # 推薦藥物
│   ├── search       # 搜尋藥物
│   └── check        # 檢查藥物交互作用
└── integrate     # 整合命令
    ├── full-pipeline # 完整診斷流程
    ├── batch         # 批次處理
    └── export        # 匯出結果
```

### 核心命令詳解

#### `clivoice diagnose from-soap`
```bash
# 從 SOAP 病歷檔案分析診斷
clivoice diagnose from-soap --soap-file soap.json

# 從文字輸入分析診斷
clivoice diagnose from-soap --text "病人胸悶兩天呼吸困難"

# 指定輸出格式
clivoice diagnose from-soap --soap-file soap.json --format json
```

#### `clivoice order generate`
```bash
# 根據診斷生成醫囑
clivoice order generate --diagnosis J20.9 --patient-age 45

# 指定醫囑類型
clivoice order generate --diagnosis J20.9 --type outpatient

# 包含詳細資訊
clivoice order generate --diagnosis J20.9 --verbose
```

#### `clivoice drug recommend`
```bash
# 根據診斷推薦藥物
clivoice drug recommend --diagnosis J20.9

# 指定藥物類別
clivoice drug recommend --diagnosis J20.9 --category respiratory

# 考慮患者條件
clivoice drug recommend --diagnosis J20.9 --patient-age 45 --allergies "penicillin"
```

#### `clivoice integrate full-pipeline`
```bash
# 完整診斷流程
clivoice integrate full-pipeline --soap-file soap.json --output report.json

# 互動模式
clivoice integrate full-pipeline --interactive

# 批次處理
clivoice integrate full-pipeline --input-dir ./soaps --output-dir ./reports
```

## 技術架構

### 模組設計

```
cli_anything/clivoice/
├── core/
│   ├── __init__.py
│   ├── diagnosis_engine.py    # 診斷引擎
│   ├── order_generator.py     # 醫囑生成器
│   ├── drug_recommender.py    # 藥物推薦器
│   ├── soap_parser.py         # SOAP 解析器
│   └── integration_orchestrator.py  # 整合協調器
├── adapters/
│   ├── __init__.py
│   ├── icd10_adapter.py       # ICD10v2 適配器
│   ├── medical_order_adapter.py  # medicalordertreeview 適配器
│   └── atc_drug_adapter.py    # ATCcodeTW 適配器
├── models/
│   ├── __init__.py
│   ├── patient.py             # 病患模型
│   ├── diagnosis.py           # 診斷模型
│   ├── medical_order.py       # 醫囑模型
│   └── drug_recommendation.py # 藥物推薦模型
├── utils/
│   ├── __init__.py
│   ├── file_utils.py          # 檔案工具
│   ├── validation.py          # 驗證工具
│   └── logging_config.py      # 日誌配置
└── cli/
    ├── __init__.py
    ├── commands.py            # CLI 命令定義
    └── clivoice_cli.py        # CLI 主入口
```

### 資料模型

```python
# 病患模型
class Patient:
    age: Optional[int]
    gender: Optional[str]
    allergies: List[str]
    medical_history: List[str]

# 診斷模型
class Diagnosis:
    icd10_code: str
    name: str
    confidence: float
    symptoms: List[str]
    recommendations: List[str]

# 醫囑模型
class MedicalOrder:
    code: str
    name: str
    description: str
    payment_standard: str
    category: str
    requirements: List[str]

# 藥物推薦模型
class DrugRecommendation:
    atc_code: str
    name: str
    dosage: str
    indications: List[str]
    contraindications: List[str]
    interactions: List[str]
```

## 整合策略

### ICD10v2 整合
- **方法**：直接讀取 `icd10-data.js` 檔案
- **優化**：建立記憶體索引加速查詢
- **搜尋**：症狀關鍵字模糊匹配

### medicalordertreeview 整合
- **方法**：呼叫 FastAPI 端點
- **端點**：`/api/v1/search`, `/api/v1/documents/{id}`
- **快取**：本地快取常用查詢結果

### ATCcodeTW 整合
- **方法**：呼叫 Flask API 端點
- **端點**：`/api/v1/clinic-drugs`, `/api/v1/clinic-categories`
- **驗證**：藥物代碼格式驗證

## 輸出格式

### JSON 輸出
```json
{
  "patient_info": {
    "age": 45,
    "gender": "M"
  },
  "soap_summary": "病人胸悶兩天呼吸困難...",
  "diagnoses": [
    {
      "icd10_code": "J20.9",
      "name": "急性支氣管炎",
      "confidence": 0.85,
      "symptoms": ["胸悶", "呼吸困難"]
    }
  ],
  "medical_orders": [
    {
      "code": "32001B",
      "name": "支氣管擴張劑吸入治療",
      "payment_standard": "500",
      "category": "呼吸治療"
    }
  ],
  "drug_recommendations": [
    {
      "atc_code": "R03AC",
      "name": "Salbutamol",
      "dosage": "100 mcg/puff, 1-2 puffs PRN",
      "indications": ["支氣管痙攣", "氣喘"]
    }
  ],
  "timestamp": "2026-03-19T10:30:00Z",
  "processing_time_ms": 1250
}
```

### 文字輸出
```
診斷結果:
  • J20.9 - 急性支氣管炎 (信心度: 85%)
    症狀: 胸悶, 呼吸困難

建議醫囑:
  • 32001B - 支氣管擴張劑吸入治療 (給付標準: 500元)
    類別: 呼吸治療

推薦藥物:
  • R03AC - Salbutamol (沙丁胺醇)
    劑量: 100 mcg/puff, 1-2 puffs PRN
    適應症: 支氣管痙攣, 氣喘
```

## 配置管理

### 環境變數
```bash
# ICD10v2 配置
export ICD10_DATA_PATH=/path/to/icd10-data.js

# medicalordertreeview 配置
export MEDICAL_ORDER_API_URL=http://localhost:5000
export MEDICAL_ORDER_API_KEY=your_api_key

# ATCcodeTW 配置
export ATC_DRUG_API_URL=http://localhost:5001
export ATC_DRUG_API_KEY=your_api_key

# 快取配置
export CACHE_ENABLED=true
export CACHE_TTL_SECONDS=3600
```

### 配置文件
```yaml
# config.yaml
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
  file: ./logs/clivoice.log
```

## 錯誤處理

### 錯誤類型
1. **輸入錯誤**：無效的 SOAP 格式、缺少必要欄位
2. **API 錯誤**：子系統 API 無法訪問、超時
3. **資料錯誤**：找不到匹配的診斷、醫囑或藥物
4. **系統錯誤**：記憶體不足、檔案權限問題

### 錯誤恢復策略
- **重試機制**：API 呼叫失敗時自動重試
- **降級策略**：某個子系統失敗時使用備用方案
- **快取回退**：API 不可用時使用快取資料
- **部分成功**：部分功能失敗時仍返回可用結果

## 效能優化

### 查詢優化
- **索引建立**：啟動時建立 ICD-10 記憶體索引
- **快取策略**：LRU 快取常用查詢結果
- **批次處理**：支援多個 SOAP 病歷批次處理
- **並行查詢**：多個子系統查詢並行執行

### 記憶體管理
- **延遲載入**：需要時才載入資料
- **分頁處理**：大量資料時分頁處理
- **資源清理**：定期清理快取和暫存檔案

## 測試策略

### 單元測試
- 診斷引擎邏輯測試
- 醫囑生成規則測試
- 藥物推薦演算法測試
- 適配器介面測試

### 整合測試
- 完整診斷流程測試
- 子系統 API 整合測試
- 錯誤處理流程測試
- 效能基準測試

### 端到端測試
- 真實 SOAP 病歷處理測試
- 批次處理流程測試
- 輸出格式驗證測試
- 使用者情境模擬測試

## 部署與維護

### 安裝方式
```bash
# PyPI 安裝
pip install cli-anything-clivoice

# 本地開發安裝
pip install -e .

# Docker 部署
docker run -d cli-anything/clivoice:latest
```

### 監控與日誌
- **健康檢查**：`clivoice health`
- **效能指標**：處理時間、成功率、錯誤率
- **審計日誌**：所有診斷操作記錄
- **警示機制**：API 失敗、效能下降警示

## 安全考量

### 資料安全
- 病患資料本地處理，不外傳
- API 金鑰加密儲存
- 敏感資料記錄遮蔽

### 合規性
- 符合醫療資料隱私法規
- 診斷建議僅供參考，需醫師確認
- 明確標示 AI 輔助生成內容

## 未來擴展

### 功能擴展
1. **多語言支援**：英文、日文診斷輸出
2. **專科特化**：內科、外科、兒科等專科模板
3. **進階分析**：疾病風險評估、治療效果預測
4. **學習功能**：根據回饋優化推薦演算法

### 技術擴展
1. **分散式部署**：支援多節點分散式處理
2. **GPU 加速**：深度學習模型加速
3. **即時更新**：線上資料庫即時同步
4. **插件系統**：第三方擴展插件支援