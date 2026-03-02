# 📖 SoapVoice API 整合文件

## 給前端開發者的整合指南

**版本:** v0.6.0  
**最後更新:** 2026-03-08  
**基礎 URL:** `http://localhost:8000` (開發環境)

---

## 🔑 快速開始

### 1. API 端點總覽

| 端點 | 方法 | 說明 |
|------|------|------|
| `/health` | GET | 服務健康檢查 |
| `/api/v1` | GET | API v1 根路徑 |
| `/api/v1/clinical/normalize` | POST | 醫療文本標準化 |
| `/api/v1/clinical/icd10` | POST | ICD-10 代碼分類 |
| `/api/v1/clinical/classify/soap` | POST | SOAP 分類 |
| `/api/v1/clinical/soap/generate` | POST | SOAP 病歷生成 |
| `/api/v1/clinical/health` | GET | 臨床 NLP 健康檢查 |

---

## 📡 API 使用範例

### 1. 健康檢查

```javascript
// 檢查服務是否可用
const response = await fetch('http://localhost:8000/health');
const data = await response.json();
// { "status": "healthy", "service": "SoapVoice API", "version": "0.1.0" }
```

### 2. 醫療文本標準化

```javascript
// 將口語中文轉換為專業英文醫療術語
const response = await fetch('http://localhost:8000/api/v1/clinical/normalize', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    text: "病人胸悶兩天還有點喘",
    context: {
      specialty: "general",  // 可選
    }
  }),
});

const data = await response.json();
/* 回應範例:
{
  "normalized_text": "病人 chest tightness 兩天還有點 dyspnea",
  "terms": [
    {
      "original": "胸悶",
      "standard": "chest tightness",
      "category": "symptom",
      "confidence": 0.95,
      "icd10_candidates": ["R07.89"]
    },
    {
      "original": "喘",
      "standard": "dyspnea",
      "category": "symptom",
      "confidence": 0.9,
      "icd10_candidates": ["R06.02"]
    }
  ],
  "processing_time_ms": 12.5
}
*/
```

### 3. ICD-10 代碼分類

```javascript
// 根據症狀描述自動映射到 ICD-10 代碼
const response = await fetch('http://localhost:8000/api/v1/clinical/icd10', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    text: "病人胸悶，呼吸困難",
    context: {
      age: 45,      // 可選 - 年齡
      gender: "M",  // 可選 - 性別 (M/F)
    }
  }),
});

const data = await response.json();
/* 回應範例:
{
  "matches": [
    {
      "code": "R07.89",
      "description": "Chest tightness",
      "description_zh": "胸悶",
      "category": "Respiratory",
      "confidence": 0.9,
      "matched_keywords": ["胸悶"]
    },
    {
      "code": "R06.02",
      "description": "Shortness of breath",
      "description_zh": "呼吸急促",
      "category": "Respiratory",
      "confidence": 0.85,
      "matched_keywords": ["呼吸困難"]
    }
  ],
  "primary_code": "R07.89",
  "processing_time_ms": 8.3
}
*/
```

### 4. SOAP 分類

```javascript
// 將醫療文本分類為 S/O/A/P 類別
const response = await fetch('http://localhost:8000/api/v1/clinical/classify/soap', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  params: {
    text: "病人說他胸悶很痛",
  },
});

const data = await response.json();
/* 回應範例:
{
  "text": "病人說他胸悶很痛",
  "category": "subjective",  // subjective/objective/assessment/plan/unknown
  "confidence": 0.75,
  "matched_keywords": ["胸悶", "痛"]
}
*/
```

### 5. SOAP 病歷生成

```javascript
// 從醫療對話記錄生成完整的 SOAP 病歷
const response = await fetch('http://localhost:8000/api/v1/clinical/soap/generate', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    transcript: "病人胸悶兩天，呼吸困難，血壓 140/90",
    patient_context: {
      age: 45,
      gender: "M",
      chief_complaint: "chest pain",  // 可選
    }
  }),
});

const data = await response.json();
/* 回應範例:
{
  "soap": {
    "subjective": "45-year-old male with chest tightness for 2 days...",
    "objective": "BP: 140/90, HR: 80...",
    "assessment": "R07.89 - Chest tightness...",
    "plan": "Further evaluation pending...",
    "conversation_summary": "病人主訴胸悶兩天伴隨呼吸困難..."
  },
  "metadata": {
    "confidence": { "subjective": 0.9, "objective": 0.85, ... },
    "model_version": "qwen3-32b"
  },
  "processing_time_ms": 2145.3
}
*/
```

---

## 🔌 JavaScript SDK (選用)

```javascript
// soapvoice-sdk.js
class SoapVoiceClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  async normalize(text, context = {}) {
    const response = await fetch(`${this.baseUrl}/api/v1/clinical/normalize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, context }),
    });
    return response.json();
  }

  async classifyICD10(text, context = {}) {
    const response = await fetch(`${this.baseUrl}/api/v1/clinical/icd10`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, context }),
    });
    return response.json();
  }

  async classifySOAP(text) {
    const response = await fetch(`${this.baseUrl}/api/v1/clinical/classify/soap?text=${encodeURIComponent(text)}`, {
      method: 'POST',
    });
    return response.json();
  }

  async generateSOAP(transcript, patientContext = {}) {
    const response = await fetch(`${this.baseUrl}/api/v1/clinical/soap/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transcript, patient_context: patientContext }),
    });
    return response.json();
  }

  async health() {
    const response = await fetch(`${this.baseUrl}/health`);
    return response.json();
  }
}

// 使用範例
const client = new SoapVoiceClient();
const result = await client.normalize("病人胸悶兩天");
console.log(result);
```

---

## 📊 效能指標

| 端點 | 平均延遲 | P95 延遲 | P99 延遲 |
|------|----------|----------|----------|
| `/health` | <10ms | <20ms | <50ms |
| `/clinical/normalize` | <50ms | <100ms | <200ms |
| `/clinical/icd10` | <50ms | <100ms | <200ms |
| `/clinical/classify/soap` | <50ms | <100ms | <200ms |
| `/clinical/soap/generate` | <3000ms | <5000ms | <8000ms |

---

## ⚠️ 錯誤處理

### 常見錯誤代碼

| 代碼 | 說明 | 處理方式 |
|------|------|----------|
| 200 | 成功 | - |
| 400 | 請求格式錯誤 | 檢查 JSON 格式和必填欄位 |
| 404 | 端點不存在 | 檢查 URL 路徑 |
| 500 | 服務器錯誤 | 檢查服務器日誌，可能是模型未載入 |

### 錯誤回應格式

```json
{
  "detail": "錯誤描述"
}
```

---

## 🔐 認證 (未來擴充)

目前開發環境不需要認證。生產環境將支援：

- API Key (Header: `X-API-Key`)
- JWT Token (Header: `Authorization: Bearer <token>`)

---

## 📝 最佳實踐

1. **錯誤處理**:  always wrap API calls in try-catch
2. **重試機制**: 對於 500 錯誤，建議實作指數退避重試
3. **快取**: 對於相同的輸入，考慮快取回應結果
4. **超時**: 設定合理的請求超時時間（建議 30 秒）
5. **並發**: 避免短時間內大量請求，建議限制並發數

---

## 🧪 測試

```bash
# 執行端到端測試
uv run python scripts/test_e2e.py

# 執行負載測試
uv run locust -f scripts/load_test.py --host=http://localhost:8000
```

---

## 📞 支援

如有問題，請查閱：
- [FastAPI 文件](https://fastapi.tiangolo.com/)
- [OpenAPI Swagger](http://localhost:8000/docs)
- [ReDoc](http://localhost:8000/redoc)
