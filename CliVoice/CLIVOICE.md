# CLIVOICE CLI Harness 規範文件

## 軟體概述

CLIVOICE 是一個醫療查詢系統集合，包含三個核心組件：
1. **ATCcodeTW** - 台灣藥品 ATC 分類查詢系統
2. **ICD10v2** - ICD-10 疾病分類碼查詢系統  
3. **medicalordertreeview** - 醫療服務給付項目及支付標準樹狀圖導航系統

## 目標用途

在 SOAP 病歷形成後，協助醫療人員：
1. **尋找正確診斷** - 透過 ICD-10 查詢系統
2. **尋找正確醫囑** - 透過醫療給付項目查詢系統
3. **尋找正確藥物** - 透過 ATC 藥品分類查詢系統

## 系統架構分析

### 1. ATCcodeTW
- **類型**: Flask Web 應用
- **數據源**: SQLite 資料庫 + CSV 檔案
- **核心功能**: 
  - ATC 藥物分類樹瀏覽
  - 藥物詳細資訊查詢
  - AI 藥物摘要
  - 藥物管理（新增/刪除/批量導入）

### 2. ICD10v2
- **類型**: 純前端 Web 應用
- **數據源**: JavaScript 資料檔案 (icd10-data.js)
- **核心功能**:
  - ICD-10 代碼搜尋（中英文）
  - 章節導航（22個章節）
  - 樹狀結構瀏覽
  - 代碼複製功能

### 3. medicalordertreeview
- **類型**: FastAPI 後端 + 前端應用
- **數據源**: Word 文檔 + JSON 配置
- **核心功能**:
  - 醫療給付項目樹狀導航
  - 全文搜尋
  - 表格數據渲染
  - 多層級檢視（Part → Chapter → Section → Item）

## CLI 架構設計

### 命令分組
```
clivoice/
├── atc/          # ATC 藥品查詢命令
├── icd10/        # ICD-10 診斷查詢命令  
├── order/        # 醫囑查詢命令
└── soap/         # SOAP 整合命令
```

### 核心命令設計

#### 1. ATC 藥品查詢
```
clivoice atc search <query>          # 搜尋藥品
clivoice atc tree                    # 顯示 ATC 分類樹
clivoice atc details <code>          # 顯示藥品詳細資訊
clivoice atc summary <code>          # 顯示 AI 藥物摘要
```

#### 2. ICD-10 診斷查詢
```
clivoice icd10 search <query>        # 搜尋 ICD-10 代碼
clivoice icd10 chapter <id>          # 顯示章節內容
clivoice icd10 details <code>        # 顯示代碼詳細資訊
clivoice icd10 validate <code>       # 驗證 ICD-10 代碼
```

#### 3. 醫囑查詢
```
clivoice order search <query>        # 搜尋醫療給付項目
clivoice order tree                  # 顯示樹狀結構
clivoice order details <id>          # 顯示項目詳細資訊
clivoice order part <part_id>        # 顯示特定部分內容
```

#### 4. SOAP 整合
```
clivoice soap analyze <text>         # 分析 SOAP 文本，建議診斷/醫囑/藥物
clivoice soap complete <file>        # 從 SOAP 檔案自動完成查詢
clivoice soap export <format>        # 匯出查詢結果
```

### 狀態模型

```python
class ClivoiceState:
    """CLIVOICE 會話狀態"""
    current_session: Optional[Session] = None
    search_history: List[SearchRecord] = []
    soap_context: Optional[SOAPContext] = None
    export_format: str = "json"
```

### 輸出格式
- **JSON**: `--json` 參數，用於 AI 代理消費
- **表格**: 預設人類可讀格式
- **CSV**: `--csv` 參數，用於數據匯出
- **Markdown**: `--md` 參數，用於文檔生成

## 技術實現策略

### 1. 數據訪問層
- **ATCcodeTW**: 直接讀取 SQLite 資料庫
- **ICD10v2**: 解析 icd10-data.js 檔案
- **medicalordertreeview**: 使用 FastAPI 端點或直接讀取 JSON 數據

### 2. 命令執行流程
```
用戶輸入 → 命令解析 → 數據查詢 → 結果格式化 → 輸出顯示
```

### 3. 錯誤處理
- 數據源不可用時提供 fallback 方案
- 網路錯誤時提供離線模式
- 輸入驗證與錯誤提示

### 4. 性能優化
- 數據快取機制
- 並行查詢支援
- 增量數據載入

## 整合工作流程

### SOAP 病歷處理流程
```
1. 接收 SOAP 文本輸入
2. 提取關鍵醫療術語
3. 並行查詢三個系統：
   - ICD-10: 診斷代碼建議
   - Order: 醫囑項目建議  
   - ATC: 藥物建議
4. 整合結果並排序
5. 輸出格式化建議
```

### 批量處理模式
```
clivoice batch process <directory>   # 批量處理 SOAP 檔案
clivoice batch analyze <csv_file>    # 分析 CSV 數據集
```

## 測試策略

### 單元測試
- 命令解析測試
- 數據查詢測試
- 格式化測試

### 整合測試
- 端到端查詢測試
- SOAP 分析測試
- 數據源連接測試

### 性能測試
- 查詢響應時間
- 並發處理能力
- 記憶體使用情況

## 部署與安裝

### 依賴管理
- 使用 `uv` 進行 Python 套件管理
- 最小化依賴，避免與現有系統衝突
- 支援虛擬環境安裝

### 配置管理
- 環境變數配置
- 數據源路徑配置
- 快取配置

## 擴展性設計

### 插件系統
- 支援自定義數據源
- 支援自定義輸出格式
- 支援自定義查詢邏輯

### API 整合
- REST API 端點
- WebSocket 即時查詢
- 批次處理 API

## 安全考量

### 數據保護
- 醫療數據加密儲存
- 查詢日誌匿名化
- 存取控制機制

### 合規性
- 符合醫療數據隱私規範
- 審計日誌記錄
- 數據使用授權管理