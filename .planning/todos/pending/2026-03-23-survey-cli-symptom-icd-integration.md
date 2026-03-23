---
created: 2026-03-23T10:55:00.000Z
title: Survey CLI for SOAP symptom/ICD/medical order/drug integration
area: tooling
files:
  - src/cli.py
  - scripts/soapvoice_engine.py
  - agent-harness/cli_anything/clivoice/
  - src/nlp/icd10_classifier.py
  - src/nlp/terminology_mapper.py
---

## Problem

目前的流程是：
1. Whisper 語音轉文字 → 中文逐字稿
2. LLM 生成 SOAP 病歷

但缺少：
- 症狀提取 (Symptom extraction) - ✅ 已有 terminology_mapper
- ICD-10 診斷代碼對應 - ✅ 已有 ICD10Classifier
- 醫囑建議 (Medical order) - ❌ 需整合
- 藥物建議 (Drug recommendation) - ❌ 需整合

## Solution

### 已有的 NLP 模組（調研結果）

1. **MedicalTerminologyMapper** (`src/nlp/terminology_mapper.py`)
   - 80+ 術語映射
   - 口語 → 標準醫療英文
   - ICD-10 候選碼

2. **ICD10Classifier** (`src/nlp/icd10_classifier.py`)
   - 50+ 症狀映射
   - 症狀 → ICD-10 代碼
   - 測試結果：
   ```
   輸入: 病人咳嗽兩天，胸悶，呼吸困難
   輸出:
     R07.89: Chest tightness (90%)
     R06.02: Shortness of breath (90%)
     R05: Cough (90%)
   ```

3. **SOAPClassifier** (`src/nlp/soap_classifier.py`)
   - 關鍵字 S/O/A/P 分類
   - 置信度計算

### 需要整合的模組

1. **醫囑建議 (Medical Order)**
   - 可整合 CliVoice 的 `medicalordertreeview`
   
2. **藥物建議 (Drug)**
   - 可整合 CliVoice 的 `ATCcodeTW`
   - 或現有 ATC 分類 (`src/db/atc_classification.py`)

### 建議 Pipeline

```
音頻 → Whisper → 症狀提取 → ICD-10 → 醫囑/藥物 → SOAP
```

**Status:** 已完成調研，建議下一步實作整合