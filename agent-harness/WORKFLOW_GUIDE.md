# CliVoice CLI 工作流程範例指南

## 簡介

本指南提供 CliVoice CLI 的實際工作流程範例，涵蓋從基本操作到進階整合的各種場景。

## 目錄

1. [基本操作](#基本操作)
2. [臨床工作流程](#臨床工作流程)
3. [資料分析工作流程](#資料分析工作流程)
4. [系統整合工作流程](#系統整合工作流程)
5. [NotebookLM 增強工作流程](#notebooklm-增強工作流程)

---

## 基本操作

### 1. 症狀查詢診斷

```bash
# 查詢咳嗽相關的 ICD-10 診斷
clivoice diagnose 咳嗽 --limit 10

# 查詢結果
# J06.9 急性上呼吸道感染
# J20.9 急性支氣管炎
# J40 支氣管炎
# ...
```

### 2. 分析 SOAP 病歷

```bash
# 分析 SOAP 格式病歷
clivoice analyze "病人主訴咳嗽、發燒三天，喉嚨痛。體溫38.5°C，喉嚨紅腫。" --json

# 輸出結果包含
# - 提取的症狀
# - 建議的 ICD-10 診斷
# - 建議的醫囑
# - 建議的藥物
```

### 3. 批次處理

```bash
# 批次處理多個病歷
clivoice batch-process patient_notes.txt --output results.json --workers 4

# 格式：每行一個病歷
# 病人A: 咳嗽發燒
# 病人B: 胃痛嘔吐
# 病人C: 頭痛暈眩
```

### 4. 互動模式

```bash
# 進入互動模式
clivoice repl

# 在 REPL 中執行多個操作
> diagnose 咳嗽
> orders J06.9
> drugs J06.9
> analyze 病人咳嗽發燒三天
> exit
```

---

## 臨床工作流程

### 流程 1: 門診病歷分析

```bash
#!/bin/bash
# 門診病歷分析腳本

# 1. 接收病人病歷
SOAP_NOTE=$1

# 2. 分析病歷
clivoice analyze "$SOAP_NOTE" --json --output analysis.json

# 3. 提取主要診斷
PRIMARY_DIAGNOSIS=$(cat analysis.json | jq -r '.primary_diagnosis')

# 4. 查詢相關醫囑
clivoice orders "$PRIMARY_DIAGNOSIS" --category 藥物 --limit 5

# 5. 查詢相關藥物
clivoice drugs "$PRIMARY_DIAGNOSIS" --limit 5

# 6. 產生報告
cat analysis.json | jq '.'
```

**使用方式:**
```bash
./outpatient_analysis.sh "病人主訴咳嗽、發燒三天"
```

### 流程 2: 急診快速評估

```bash
#!/bin/bash
# 急診快速評估腳本

SYMPTOMS=$1

# 即時搜尋可能診斷
clivoice diagnose "$SYMPTOMS" --limit 5 --json

# 對每個診斷快速查詢
DIAGNOSES=$(clivoice diagnose "$SYMPTOMS" --limit 5 --json)

echo "$DIAGNOSES" | jq -r '.[].code' | while read CODE; do
    echo "=== $CODE 的緊急處置 ==="
    clivoice orders "$CODE" --category 緊急 --limit 3
done
```

**使用方式:**
```bash
./emergency_assessment.sh "胸痛、呼吸困難、冷汗"
```

### 流程 3: 慢性病追蹤

```bash
#!/bin/bash
# 慢性病追蹤腳本

PATIENT_ID=$1
DIAGNOSIS=$2

echo "=== 病人 $PATIENT_ID 慢性病追蹤 ==="
echo "診斷: $DIAGNOSIS"

# 查詢最新治療方案
echo "=== 最新治療方案 ==="
clivoice orders "$DIAGNOSIS" --limit 10

# 查詢藥物調整建議
echo "=== 藥物建議 ==="
clivoice drugs "$DIAGNOSIS" --limit 5

# 查詢追蹤項目
echo "=== 追蹤檢查項目 ==="
clivoice orders "$DIAGNOSIS" --category 檢查 --limit 5
```

**使用方式:**
```bash
./chronic_care.sh P12345 "E11.9 第二型糖尿病"
```

---

## 資料分析工作流程

### 流程 1: 日報統計

```bash
#!/bin/bash
# 每日病歷統計腳本

REPORT_DATE=${1:-$(date +%Y-%m-%d)}
INPUT_FILE="data/soap_notes_${REPORT_DATE}.txt"
OUTPUT_DIR="reports/${REPORT_DATE}"

# 建立輸出目錄
mkdir -p "$OUTPUT_DIR"

# 批次分析
clivoice batch-process "$INPUT_FILE" --output "${OUTPUT_DIR}/analysis.json"

# 產生統計報告
python3 << 'EOF'
import json
from collections import Counter

with open("reports/${REPORT_DATE}/analysis.json") as f:
    data = json.load(f)

# 診斷統計
diagnoses = [d['code'] for p in data for d in p['diagnoses']]
diagnosis_counts = Counter(diagnoses)

print("=" * 60)
print("每日病歷統計報告 - ${REPORT_DATE}")
print("=" * 60)
print(f"\n總病歷數: {len(data)}")
print(f"總診斷數: {len(diagnoses)}")
print("\n前十大常見診斷:")
for code, count in diagnosis_counts.most_common(10):
    print(f"  {code}: {count} 次")
EOF
```

### 流程 2: 疾病分布分析

```bash
#!/bin/bash
# 疾病分布分析腳本

PERIOD=$1  # 例如: 2024-Q1

# 分析指定期間的病歷
clivoice batch-process "data/period_${PERIOD}.txt" \
    --output "analysis_${PERIOD}.json" \
    --format json

# 產生分布圖表
python3 << 'EOF'
import json
import matplotlib.pyplot as plt

with open("analysis_${PERIOD}.json") as f:
    data = json.load(f)

# 收集診斷
diagnoses = []
for patient in data:
    for diagnosis in patient['diagnoses']:
        diagnoses.append(diagnosis['name'])

# 計算分布
from collections import Counter
dist = Counter(diagnoses).most_common(15)

# 繪製長條圖
names, counts = zip(*dist)
plt.figure(figsize=(12, 6))
plt.barh(names, counts)
plt.xlabel('病例數')
plt.title('疾病分布分析 - ${PERIOD}')
plt.tight_layout()
plt.savefig('disease_distribution_${PERIOD}.png')
print("圖表已儲存: disease_distribution_${PERIOD}.png")
EOF
```

### 流程 3: 醫療資源使用分析

```bash
#!/bin/bash
# 醫療資源使用分析腳本

# 分析所有病歷的醫囑
clivoice batch-process "data/all_notes.txt" \
    --output "full_analysis.json"

# 分析資源使用
python3 << 'EOF'
import json

with open("full_analysis.json") as f:
    data = json.load(f)

# 統計醫囑類別
order_categories = {}
for patient in data:
    for order in patient['orders']:
        category = order.get('category', '其他')
        order_categories[category] = order_categories.get(category, 0) + 1

print("醫療資源使用統計")
print("=" * 60)
for category, count in sorted(order_categories.items(), key=lambda x: x[1], reverse=True):
    print(f"{category}: {count} 次")

# 計算平均費用
total_fees = sum(sum(o.get('fee', 0) for o in p['orders']) for p in data)
avg_fee = total_fees / len(data) if data else 0
print(f"\n平均每人醫療費用: {avg_fee:.2f} 元")
EOF
```

---

## 系統整合工作流程

### 流程 1: 與電子病歷系統 (EMR) 整合

```python
#!/usr/bin/env python3
"""
EMR 整合範例

從 EMR 系統讀取病歷，分析後寫回診斷建議
"""

import requests
import json
from cli_anything.clivoice import IntegrationOrchestrator

class EMRIntegration:
    def __init__(self, emr_api_url: str, emr_api_key: str):
        self.emr_api_url = emr_api_url
        self.emr_api_key = emr_api_key
        self.orchestrator = IntegrationOrchestrator()
    
    def get_patient_note(self, patient_id: str) -> dict:
        """從 EMR 取得病人病歷"""
        response = requests.get(
            f"{self.emr_api_url}/patients/{patient_id}/notes",
            headers={"Authorization": f"Bearer {self.emr_api_key}"}
        )
        return response.json()
    
    def analyze_and_suggest(self, patient_id: str) -> dict:
        """分析病歷並建議"""
        # 取得病歷
        note = self.get_patient_note(patient_id)
        
        # 分析病歷
        result = self.orchestrator.process_soap_note(note['content'])
        
        # 格式化建議
        suggestions = {
            "patient_id": patient_id,
            "primary_diagnosis": result.diagnoses[0].to_dict() if result.diagnoses else None,
            "suggested_orders": [o.to_dict() for o in result.orders[:5]],
            "suggested_drugs": [d.to_dict() for d in result.drug_recommendations[:5]],
            "confidence": result.confidence
        }
        
        return suggestions
    
    def update_emr(self, patient_id: str, suggestions: dict):
        """更新 EMR 系統"""
        requests.post(
            f"{self.emr_api_url}/patients/{patient_id}/diagnoses",
            headers={"Authorization": f"Bearer {self.emr_api_key}"},
            json=suggestions
        )

# 使用範例
emr = EMRIntegration(
    emr_api_url="https://emr.hospital.org/api",
    emr_api_key="your-api-key"
)

suggestions = emr.analyze_and_suggest("P12345")
print(json.dumps(suggestions, indent=2, ensure_ascii=False))
```

### 流程 2: 與醫療資訊系統 (HIS) 整合

```python
#!/usr/bin/env python3
"""
HIS 整合範例

與醫療資訊系統整合，自動產生醫囑和處方
"""

from cli_anything.clivoice import IntegrationOrchestrator
import json

class HISIntegration:
    def __init__(self):
        self.orchestrator = IntegrationOrchestrator()
    
    def create_order_sets(self, diagnosis_code: str) -> list:
        """建立標準醫囑套餐"""
        result = self.orchestrator.diagnosis_engine.get_orders(diagnosis_code)
        
        order_sets = []
        for order in result[:10]:
            order_set = {
                "code": order.code,
                "name": order.name,
                "category": order.category,
                "standard_dosage": order.standard_dosage,
                "frequency": "QD",  # 每日一次
                "route": "PO",      # 口服
                "duration": "7 days"
            }
            order_sets.append(order_set)
        
        return order_sets
    
    def create_prescription(self, diagnosis_code: str, patient_weight: float) -> dict:
        """建立處方"""
        drugs = self.orchestrator.drug_recommender.recommend(diagnosis_code)
        
        prescriptions = []
        for drug in drugs[:5]:
            # 根據體重調整劑量（範例）
            dosage = self._calculate_dosage(drug, patient_weight)
            
            prescription = {
                "drug_code": drug.code,
                "drug_name": drug.name,
                "dosage": dosage,
                "frequency": drug.frequency,
                "route": drug.route,
                "duration": "7 days",
                "instructions": drug.instructions
            }
            prescriptions.append(prescription)
        
        return {
            "diagnosis_code": diagnosis_code,
            "prescriptions": prescriptions
        }
    
    def _calculate_dosage(self, drug, weight: float) -> str:
        """計算劑量"""
        base_dose = drug.default_dose
        adjusted_dose = base_dose * (weight / 70)  # 根據體重調整
        return f"{adjusted_dose:.1f}{drug.unit}"

# 使用範例
his = HISIntegration()
orders = his.create_order_sets("J06.9")
prescription = his.create_prescription("J06.9", 65.0)

print("醫囑套餐:")
print(json.dumps(orders, indent=2, ensure_ascii=False))
print("\n處方:")
print(json.dumps(prescription, indent=2, ensure_ascii=False))
```

### 流程 3: 與健保系統整合

```python
#!/usr/bin/env python3
"""
健保整合範例

驗證診斷和醫囑是否符合健保規範
"""

from cli_anything.clivoice import IntegrationOrchestrator
import json

class NHICIntegration:
    def __init__(self):
        self.orchestrator = IntegrationOrchestrator()
        self.nhic_rules = self._load_nhic_rules()
    
    def _load_nhic_rules(self) -> dict:
        """載入健保規範（簡化範例）"""
        return {
            "J06.9": {
                "allowed_orders": ["A001", "A002", "B001"],
                "allowed_drugs": ["N02BA01", "R05DA04"],
                "max_days": 7,
                "requires_lab": False
            }
        }
    
    def validate_diagnosis(self, diagnosis_code: str, symptoms: str) -> dict:
        """驗證診斷是否符合健保規範"""
        rules = self.nhic_rules.get(diagnosis_code, {})
        
        # 檢查症狀是否符合診斷
        is_valid = self._check_symptom_match(diagnosis_code, symptoms)
        
        return {
            "diagnosis_code": diagnosis_code,
            "is_valid": is_valid,
            "rules": rules,
            "warnings": [] if is_valid else ["症狀與診斷不符"]
        }
    
    def validate_orders(self, diagnosis_code: str, orders: list) -> dict:
        """驗證醫囑是否符合健保規範"""
        rules = self.nhic_rules.get(diagnosis_code, {})
        allowed_orders = rules.get("allowed_orders", [])
        
        validated_orders = []
        warnings = []
        
        for order in orders:
            if order['code'] in allowed_orders:
                validated_orders.append({**order, "status": "approved"})
            else:
                validated_orders.append({**order, "status": "requires_review"})
                warnings.append(f"醫囑 {order['code']} 需要事前審查")
        
        return {
            "diagnosis_code": diagnosis_code,
            "validated_orders": validated_orders,
            "warnings": warnings,
            "approval_status": "approved" if not warnings else "partial"
        }
    
    def _check_symptom_match(self, diagnosis_code: str, symptoms: str) -> bool:
        """檢查症狀是否符合診斷（簡化實作）"""
        # 實際應使用更複雜的 NLP 或專家系統
        return True

# 使用範例
nhic = NHICIntegration()

# 驗證診斷
diag_validation = nhic.validate_diagnosis("J06.9", "咳嗽、發燒、喉嚨痛")
print("診斷驗證:")
print(json.dumps(diag_validation, indent=2, ensure_ascii=False))

# 驗證醫囑
order_validation = nhic.validate_orders("J06.9", [
    {"code": "A001", "name": "診察"},
    {"code": "B001", "name": "血液檢查"}
])
print("\n醫囑驗證:")
print(json.dumps(order_validation, indent=2, ensure_ascii=False))
```

---

## NotebookLM 增強工作流程

### 流程 1: 症狀到完整建議

```python
#!/usr/bin/env python3
"""
NotebookLM 增強工作流程 - 症狀到完整建議

使用 NotebookLM 深度搜尋，從症狀到完整的臨床建議
"""

from cli_anything.clivoice.adapters.notebooklm_adapter import NotebookLMAdapter
from cli_anything.clivoice import IntegrationOrchestrator
import json

class EnhancedClinicalWorkflow:
    def __init__(self):
        self.notebooklm = NotebookLMAdapter()
        self.orchestrator = IntegrationOrchestrator()
    
    def process_symptoms(self, symptoms: str, patient_context: str = None) -> dict:
        """處理症狀到完整臨床建議"""
        result = {
            "symptoms": symptoms,
            "patient_context": patient_context,
            "datetime": self._get_current_datetime()
        }
        
        # Step 1: 搜尋相關診斷
        print("[1/5] 搜尋可能診斷...")
        diagnoses = self.notebooklm.search_symptoms(symptoms, max_results=5)
        result["notebooklm_diagnoses"] = diagnoses
        
        if diagnoses:
            primary_diagnosis = diagnoses[0]
            result["primary_diagnosis"] = primary_diagnosis
            
            # Step 2: 搜尋治療方案
            print("[2/5] 搜尋治療方案...")
            treatments = self.notebooklm.search_treatment_protocols(
                primary_diagnosis['content'], max_results=5
            )
            result["treatment_protocols"] = treatments
            
            # Step 3: 搜尋藥物建議
            print("[3/5] 搜尋藥物建議...")
            drugs = self.notebooklm.search_drug_recommendations(
                primary_diagnosis['content'], max_results=5
            )
            result["drug_recommendations"] = drugs
            
            # Step 4: 增強診斷資訊
            print("[4/5] 增強診斷資訊...")
            enhanced = self.notebooklm.enhance_diagnosis(
                self._extract_icd_code(primary_diagnosis),
                self._extract_diagnosis_name(primary_diagnosis)
            )
            result["enhanced_diagnosis"] = enhanced
            
            # Step 5: 整合 CliVoice 本地資料庫
            print("[5/5] 整合本地資料庫...")
            local_result = self.orchestrator.diagnosis_engine.find_diagnoses(symptoms)
            result["local_diagnoses"] = [d.to_dict() for d in local_result[:5]]
        
        return result
    
    def _extract_icd_code(self, diagnosis: dict) -> str:
        """從診斷內容提取 ICD 代碼"""
        content = diagnosis.get('content', '')
        # 簡化實作，實際應使用正規表達式
        import re
        match = re.search(r'\(([A-Z]\d+\.?\d*)\)', content)
        return match.group(1) if match else 'Unknown'
    
    def _extract_diagnosis_name(self, diagnosis: dict) -> str:
        """從診斷內容提取診斷名稱"""
        content = diagnosis.get('content', '')
        # 移除 ICD 代碼部分
        import re
        return re.sub(r'\s*\([A-Z]\d+\.?\d*\)\s*', '', content).strip()
    
    def _get_current_datetime(self) -> str:
        """取得目前日期時間"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def generate_report(self, result: dict) -> str:
        """產生臨床報告"""
        report = []
        report.append("=" * 60)
        report.append("Enhanced Clinical Report")
        report.append("=" * 60)
        report.append(f"DateTime: {result['datetime']}")
        report.append(f"Symptoms: {result['symptoms']}")
        
        if result.get('primary_diagnosis'):
            report.append(f"\nPrimary Diagnosis: {result['primary_diagnosis']['content']}")
            report.append(f"Confidence: {result['primary_diagnosis'].get('confidence', 0):.2f}")
        
        if result.get('treatment_protocols'):
            report.append(f"\nTreatment Protocols ({len(result['treatment_protocols'])}):")
            for i, t in enumerate(result['treatment_protocols'][:3], 1):
                report.append(f"  {i}. {t['content']}")
        
        if result.get('drug_recommendations'):
            report.append(f"\nDrug Recommendations ({len(result['drug_recommendations'])}):")
            for i, d in enumerate(result['drug_recommendations'][:3], 1):
                report.append(f"  {i}. {d['content']}")
        
        if result.get('enhanced_diagnosis'):
            ed = result['enhanced_diagnosis']
            report.append(f"\nEnhanced Information:")
            report.append(f"  Epidemiology: {ed['enhanced_info']['epidemiology']}")
            report.append(f"  Clinical Features: {ed['enhanced_info']['clinical_features']}")
            report.append(f"  Diagnostic Criteria: {ed['enhanced_info']['diagnostic_criteria']}")
        
        report.append("=" * 60)
        return "\n".join(report)

# 使用範例
workflow = EnhancedClinicalWorkflow()

# 處理症狀
symptoms = "咳嗽、發燒 38.5 度、全身酸痛、喉嚨痛、疲倦"
result = workflow.process_symptoms(symptoms, patient_context="40歲男性，無慢性病史")

# 產生報告
report = workflow.generate_report(result)
print(report)

# 儲存為 JSON
with open('enhanced_clinical_report.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("\n完整報告已儲存至: enhanced_clinical_report.json")
```

### 流程 2: 診斷增強與文獻回顧

```python
#!/usr/bin/env python3
"""
NotebookLM 增強工作流程 - 診斷增強與文獻回顧

使用 NotebookLM 為既有診斷增強資訊並進行文獻回顧
"""

from cli_anything.clivoice.adapters.notebooklm_adapter import NotebookLMAdapter
import json

class DiagnosisEnhancementWorkflow:
    def __init__(self):
        self.notebooklm = NotebookLMAdapter()
    
    def enhance_diagnosis_with_literature(self, diagnosis_code: str, 
                                          diagnosis_name: str) -> dict:
        """增強診斷並進行文獻回顧"""
        result = {
            "diagnosis_code": diagnosis_code,
            "diagnosis_name": diagnosis_name,
            "literature_review": {}
        }
        
        # 增強診斷資訊
        print(f"增強診斷: {diagnosis_name} ({diagnosis_code})...")
        enhanced = self.notebooklm.enhance_diagnosis(diagnosis_code, diagnosis_name)
        result["enhanced_info"] = enhanced
        
        # 文獻回顧 - 治療指引
        print("搜尋治療指引...")
        guidelines = self.notebooklm.search_treatment_protocols(
            f"{diagnosis_name} ({diagnosis_code}) 治療指引", max_results=5
        )
        result["literature_review"]["guidelines"] = guidelines
        
        # 文獻回顧 - 最新研究
        print("搜尋最新研究...")
        research = self.notebooklm.search_medical_database(
            NotebookLMQuery(
                query=f"{diagnosis_name} 最新研究進展",
                context="請提供近五年內的臨床研究報告",
                max_results=5
            )
        )
        result["literature_review"]["research"] = research
        
        # 文獻回顧 - 藥物治療
        print("搜尋藥物治療文獻...")
        drug_literature = self.notebooklm.search_drug_recommendations(
            f"{diagnosis_name} 藥物治療", max_results=5
        )
        result["literature_review"]["drug_therapy"] = drug_literature
        
        return result
    
    def compare_diagnoses(self, diagnoses: list) -> dict:
        """比較多個診斷"""
        comparison = {
            "diagnoses": [],
            "summary": {}
        }
        
        for diag in diagnoses:
            code = diag['code']
            name = diag['name']
            
            enhanced = self.notebooklm.enhance_diagnosis(code, name)
            comparison["diagnoses"].append({
                "code": code,
                "name": name,
                "confidence": enhanced['confidence'],
                "evidence_summary": enhanced['enhanced_info']['evidence_summary']
            })
        
        # 計算整體信心
        confidences = [d['confidence'] for d in comparison["diagnoses"]]
        comparison["summary"]["average_confidence"] = sum(confidences) / len(confidences)
        comparison["summary"]["max_confidence"] = max(confidences)
        comparison["summary"]["differential_diagnoses"] = len(diagnoses)
        
        return comparison

# 使用範例
workflow = DiagnosisEnhancementWorkflow()

# 單一診斷增強
diagnosis = workflow.enhance_diagnosis_with_literature(
    "J11.1",
    "流感"
)

print("診斷增強結果:")
print(json.dumps(diagnosis, indent=2, ensure_ascii=False))

# 儲存報告
with open('diagnosis_enhancement_report.json', 'w', encoding='utf-8') as f:
    json.dump(diagnosis, f, ensure_ascii=False, indent=2)
print("\n報告已儲存至: diagnosis_enhancement_report.json")
```

---

## 自動化腳本範例

### 每日自動化腳本

```bash
#!/bin/bash
# 每日自動化工作腳本

# 設定
REPORT_DATE=$(date +%Y-%m-%d)
DATA_DIR="/data/soap_notes"
OUTPUT_DIR="/reports/${REPORT_DATE}"

# 建立輸出目錄
mkdir -p "${OUTPUT_DIR}"

# 1. 接收昨日病歷
echo "[1/5] 同步病歷資料..."
cp "${DATA_DIR}/notes_${REPORT_DATE}.txt" "${OUTPUT_DIR}/" 2>/dev/null || echo "無新病歷"

# 2. 批次分析
echo "[2/5] 分析病歷..."
if [ -f "${OUTPUT_DIR}/notes_${REPORT_DATE}.txt" ]; then
    clivoice batch-process "${OUTPUT_DIR}/notes_${REPORT_DATE}.txt" \
        --output "${OUTPUT_DIR}/analysis.json"
fi

# 3. NotebookLM 增強搜尋
echo "[3/5] NotebookLM 深度搜尋..."
python3 << 'PYTHON'
import json
import sys

with open("${OUTPUT_DIR}/analysis.json") as f:
    data = json.load(f)

from cli_anything.clivoice.adapters.notebooklm_adapter import NotebookLMAdapter

notebooklm = NotebookLMAdapter()
enhanced_data = []

for patient in data[:10]:  # 限制前10筆
    symptoms = patient.get('symptoms', '')
    if symptoms:
        result = notebooklm.search_symptoms(symptoms, max_results=3)
        patient['notebooklm_diagnoses'] = result
        enhanced_data.append(patient)

with open("${OUTPUT_DIR}/enhanced_analysis.json", 'w') as f:
    json.dump(enhanced_data, f, ensure_ascii=False, indent=2)
PYTHON

# 4. 產生統計報告
echo "[4/5] 產生統計報告..."
python3 << 'PYTHON'
import json
from collections import Counter

with open("${OUTPUT_DIR}/enhanced_analysis.json") as f:
    data = json.load(f)

diagnoses = []
for p in data:
    for d in p.get('diagnoses', []):
        diagnoses.append(d.get('name', ''))

counter = Counter(diagnoses)

print(f"\n總病歷數: {len(data)}")
print(f"總診斷數: {len(diagnoses)}")
print("\n常見診斷:")
for name, count in counter.most_common(5):
    print(f"  {name}: {count}")
PYTHON

# 5. 發送通知
echo "[5/5] 發送通知..."
# echo "每日病歷分析報告已完成" | mail -s "Report ${REPORT_DATE}" admin@hospital.org

echo "\n完成! 報告位於: ${OUTPUT_DIR}/"
```

---

## 疑難排解

### 常見問題

1. **NotebookLM CLI 未安裝**
   ```bash
   pip install notebooklm-mcp-cli
   ```

2. **API 連線逾時**
   ```python
   # 增加逾時時間
   adapter = NotebookLMAdapter(config={"timeout": 60})
   ```

3. **快取造成資料過舊**
   ```bash
   rm -rf ~/.cache/clivoice/notebooklm/
   ```

4. **批次處理失敗**
   ```bash
   # 使用 skip-errors 選項
   clivoice batch-process input.txt --skip-errors --output results.json
   ```

---

## 授權與支援

- 授權: MIT License
- 文件: 請參考各模組的 README.md
- 問題回報: GitHub Issues
