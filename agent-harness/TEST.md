# CliVoice 測試文件

## 測試架構

CliVoice 使用 pytest 作為測試框架，測試檔案位於 `cli_anything/clivoice/tests/` 目錄中。

### 測試檔案結構

```
tests/
├── test_models.py          # 資料模型測試
├── test_core_engines.py    # 核心引擎測試
├── test_adapters.py        # 適配器測試 (待實作)
├── test_cli.py             # CLI 介面測試 (待實作)
└── test_integration.py     # 整合測試 (待實作)
```

## 執行測試

### 安裝測試依賴

```bash
cd /home/hsu/Desktop/SoapVoice/agent-harness
uv pip install pytest pytest-asyncio pytest-cov
```

### 執行所有測試

```bash
cd /home/hsu/Desktop/SoapVoice/agent-harness
python -m pytest cli_anything/clivoice/tests/ -v
```

### 執行特定測試類別

```bash
# 執行模型測試
python -m pytest cli_anything/clivoice/tests/test_models.py -v

# 執行核心引擎測試
python -m pytest cli_anything/clivoice/tests/test_core_engines.py -v
```

### 執行測試並產生覆蓋率報告

```bash
python -m pytest cli_anything/clivoice/tests/ --cov=cli_anything.clivoice --cov-report=html --cov-report=term
```

## 測試類別說明

### 1. 資料模型測試 (`test_models.py`)

測試所有資料模型的建立、驗證和序列化功能。

**包含的測試：**
- `TestPatientModel`: 病人模型測試
- `TestDiagnosisModel`: 診斷模型測試  
- `TestMedicalOrderModel`: 醫療訂單模型測試
- `TestDrugRecommendationModel`: 藥物推薦模型測試
- `TestSOAPNoteModel`: SOAP 病歷模型測試

**測試項目：**
- 模型建立與屬性驗證
- 字典轉換 (`to_dict()`)
- SOAP 病歷文字解析
- 資料驗證與預設值

### 2. 核心引擎測試 (`test_core_engines.py`)

測試核心業務邏輯引擎的功能。

**包含的測試：**
- `TestDiagnosisEngine`: 診斷引擎測試
- `TestOrderGenerator`: 醫囑生成器測試
- `TestDrugRecommender`: 藥物推薦器測試
- `TestIntegrationOrchestrator`: 整合協調器測試

**測試項目：**
- 症狀提取與診斷匹配
- 醫囑生成與優先級篩選
- 藥物推薦與處方箋生成
- 完整流程整合與報告生成

## 測試資料

測試使用範例資料，不依賴外部系統連線：

### 範例診斷資料
- `J06.9`: 急性上呼吸道感染
- `J20.9`: 急性支氣管炎  
- `K29.70`: 胃炎

### 範例醫囑資料
- 診斷類別: 一般診察費、喉部檢查、胸部X光檢查
- 藥物類別: 感冒藥、支氣管擴張劑、胃藥
- 衛教類別: 飲食衛教

### 範例藥物資料
- 解熱鎮痛藥: 乙醯胺酚、布洛芬
- 抗生素: 阿莫西林
- 呼吸系統藥: 沙丁胺醇
- 消化系統藥: 奧美拉唑、雷尼替丁

## 測試覆蓋率目標

| 模組 | 目標覆蓋率 | 目前狀態 |
|------|------------|----------|
| 資料模型 | 95% | ✅ 已完成 |
| 核心引擎 | 85% | ✅ 已完成 |
| 適配器 | 80% | ⏳ 待實作 |
| CLI 介面 | 75% | ⏳ 待實作 |
| 整合測試 | 70% | ⏳ 待實作 |

## 測試最佳實踐

### 1. 單元測試原則
- 每個測試只測試一個功能
- 使用明確的測試名稱
- 包含正向和負向測試案例
- 使用適當的斷言訊息

### 2. 測試隔離
- 測試之間互相獨立
- 使用 `setup_method` 和 `teardown_method`
- 避免測試順序依賴

### 3. 測試資料管理
- 使用範例資料而非真實資料
- 測試資料與業務邏輯分離
- 可重複使用的測試資料夾具

## 待實作的測試

### 1. 適配器測試 (`test_adapters.py`)
- `TestICD10Adapter`: ICD-10 適配器測試
- `TestMedicalOrderAdapter`: 醫療訂單適配器測試
- `TestATCDrugAdapter`: ATC 藥物適配器測試

### 2. CLI 介面測試 (`test_cli.py`)
- 命令列參數解析測試
- 輸出格式測試 (JSON/Text/Markdown)
- 錯誤處理測試

### 3. 整合測試 (`test_integration.py`)
- 端到端流程測試
- 系統整合測試
- 效能與壓力測試

## 測試執行環境

### 必要條件
- Python 3.11+
- pytest 7.0+
- 無需外部服務連線 (使用範例資料)

### 環境變數
測試不需要特殊環境變數，所有設定使用預設值。

## 疑難排解

### 常見問題

1. **導入錯誤**
   ```
   ModuleNotFoundError: No module named 'cli_anything'
   ```
   解決方案：確保從專案根目錄執行測試

2. **測試失敗**
   - 檢查測試資料是否正確
   - 確認模型定義與測試一致
   - 查看錯誤訊息中的詳細資訊

3. **覆蓋率報告問題**
   - 確保安裝 `pytest-cov`
   - 檢查 `--cov` 參數指定的模組路徑

### 測試除錯

```bash
# 顯示詳細錯誤資訊
python -m pytest cli_anything/clivoice/tests/ -v --tb=short

# 執行特定測試函數
python -m pytest cli_anything/clivoice/tests/test_models.py::TestPatientModel::test_patient_creation -v

# 使用 pdb 除錯
python -m pytest cli_anything/clivoice/tests/ --pdb
```

## 持續整合

建議在 CI/CD 流程中加入以下測試命令：

```yaml
# GitHub Actions 範例
- name: Run tests
  run: |
    cd agent-harness
    python -m pytest cli_anything/clivoice/tests/ --cov=cli_anything.clivoice --cov-fail-under=80
```

## 測試維護

### 新增測試
1. 在適當的測試檔案中新增測試類別或函數
2. 遵循現有的命名慣例
3. 包含完整的測試案例
4. 更新測試文件

### 更新測試
1. 當業務邏輯變更時更新相關測試
2. 保持測試與實際功能一致
3. 更新測試資料以反映真實使用場景

### 測試審查
- 定期審查測試覆蓋率
- 確保測試反映實際使用情況
- 移除過時或無效的測試