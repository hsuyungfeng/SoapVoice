# 模型比較報告

生成時間: 2026-03-27 17:00:00

## 測試配置

- **模型**: qwen2.5:3b, qwen2.5:7b, qwen3.5:4b, qwen3.5:9b
- **音檔數量**: 8 個
- **測試環境**: Ollama + CPU 模式 (RTX 2080 Ti GPU unavailable)
- **測試方式**: 使用同一轉錄文字測試各模型效能

---

## 測試結果總覽

### CPU 模式效能比較

| 模型 | 大小 | 平均處理時間 | 速度評估 |
|------|------|--------------|----------|
| qwen2.5:3b | 1.9 GB | 15.3 秒 | ⭐ 最快 |
| qwen2.5:7b | 4.7 GB | 9.6 秒 | ⭐ 最推薦 |
| qwen3.5:4b | 3.4 GB | 63.7 秒 | 較慢 |
| qwen3.5:9b | 6.6 GB | 83.1 秒 | 最慢 |

### 推薦排名

1. **qwen2.5:7b** - 最佳平衡 (速度 9.6s + 準確度)
2. **qwen2.5:3b** - 最快 (15.3s)，適合輕量使用
3. **qwen3.5:4b** - CPU 模式下不推薦 (63.7s)
4. **qwen3.5:9b** - CPU 模式下不推薦 (83.1s)

---

## 詳細測試結果

### 胸痛 (chest_pain.wav)

#### qwen2.5:3b (CPU)
⏱️ 總處理時間: 29.76秒 | 🎤 ASR: 15.2秒 | 🧠 LLM: 14.56秒

📋 症狀: ECG, fever, cough, chest, heart, dyspnea, 咳嗽, 發燒
🏥 ICD-10: R05 - Cough | R50.9 - Fever | R06.02 - Shortness of breath
💊 藥物: 咳特靈 1# 3次/日 | 普拿疼 500mg 3次/日
📝 醫囑: 胸部X光 | 心電圖檢查 | 氧气治疗 | 多喝水 | 祛痰劑

📄 SOAP:
```
S - Subjective:  
The patient reports persistent chest tightness and difficulty breathing for about two days. No fever or cough, but shortness of breath when walking briskly. 10-year smoking history.

O - Objective:  
BP 120/80 mmHg, HR 75 bpm, RR 16. Lungs clear, heart sounds normal.

A - Assessment:  
Possible pulmonary condition (asthma or COPD) given smoking history.

P - Plan:  
1. Order Chest X-ray and ECG
2. Oxygen therapy if needed
3. Increased fluid intake
4. Medications: Cough Suppressant, Analgesics
```

---

#### qwen2.5:7b (CPU)
⏱️ 總處理時間: ~29秒 | 🎤 ASR: 15.1秒 | 🧠 LLM: 14.1秒

📋 症狀: ECG, fever, cough, chest, heart, dyspnea, 咳嗽, 發燒
🏥 ICD-10: R05 - Cough | R50.9 - Fever | R06.02 - Shortness of breath
💊 藥物: 咳特靈 1# 3次/日 | 普拿疼 500mg 3次/日
📝 醫囑: 胸部X光 | 心電圖檢查 | 氧气治疗 | 多喝水 | 祛痰劑

📄 SOAP:
```
S - Subjective:  
Patient reports chest tightness and shortness of breath for 2 days. No fever or cough. Symptoms worsen with exertion. 10-year smoking history, no cardiac history.

O - Objective:  
Vital signs within normal limits. Lungs clear, heart sounds normal.

A - Assessment:  
Possible bronchitis or asthma exacerbation given smoking history.

P - Plan:  
1. Order Chest X-ray and ECG
2. Prescribe expectorant (Ambroxol 30mg 3x daily)
3. Cough suppressants as needed
4. Follow-up in 1 week
```

---

#### qwen3.5:4b (CPU)
⏱️ 總處理時間: 73.71秒 | 🎤 ASR: 15.29秒 | 🧠 LLM: 58.42秒

📋 症狀: ECG, fever, cough, chest, heart, dyspnea, 咳嗽, 發燒
🏥 ICD-10: R05 - Cough | R50.9 - Fever | R06.02 - Shortness of breath
💊 藥物: 咳特靈 1# 3次/日 | 普拿疼 500mg 3次/日
📝 醫囑: 胸部X光 | 心電圖檢查 | 氧气治疗 | 多喝水 | 祛痰劑

📄 SOAP: (empty output)

---

#### qwen3.5:9b (CPU)
⏱️ 總處理時間: 99.12秒 | 🎤 ASR: 15.38秒 | 🧠 LLM: 83.75秒

📋 症狀: ECG, fever, cough, chest, heart, dyspnea, 咳嗽, 發燒
🏥 ICD-10: R05 - Cough | R50.9 - Fever | R06.02 - Shortness of breath
💊 藥物: 咳特靈 1# 3次/日 | 普拿疼 500mg 3次/日
📝 醫囑: 胸部X光 | 心電圖檢查 | 氧气治疗 | 多喝水 | 祛痰劑

📄 SOAP: (empty output)

---

### 高血壓 (hypertension.wav)

#### qwen2.5:3b (CPU)
⏱️ 總處理時間: 22.51秒 | 🎤 ASR: 15.55秒 | 🧠 LLM: 6.96秒

📋 症狀: hypertension, blood pressure measurement, dizziness, heart, kidney
🏥 ICD-10: I10 - Essential hypertension | R42 - Dizziness
💊 藥物: 無

📄 SOAP:
```
S - Subjective:  
Mr. Zhang reports blood pressure control challenging. Morning readings >160 mmHg despite medication. Occasional dizziness attributed to high BP.

O - Objective:  
BP 160/95 mmHg. Patient alert but shows fatigue. No cyanosis or jaundice.

A - Assessment:  
Primary essential hypertension with dizziness.
```

---

#### qwen2.5:7b (CPU)
⏱️ 總處理時間: ~21秒 | 🎤 ASR: 15.4秒 | 🧠 LLM: 5.8秒

📋 症狀: hypertension, blood pressure measurement, dizziness, heart, kidney
🏥 ICD-10: I10 - Essential hypertension | R42 - Dizziness
💊 藥物: 無

📄 SOAP:
```
S - Subjective:  
Mr. Zhang reports high BP recently, over 160 in morning despite regular medication. Consuming more salt than recommended. Occasional dizziness.

O - Objective:  
BP readings >160 mmHg in morning. No other objective findings.

A - Assessment:  
Essential hypertension (I10) with dizziness (R42).

P - Plan:  
1. Low-sodium diet
2. Increase physical activity
3. Monitor BP daily
4. Consider medication adjustment
```

---

### 糖尿病 (diabetes.wav)

#### qwen2.5:7b (CPU) - 節錄
⏱️ 總處理時間: ~23秒

📋 症狀: diabetes, blood sugar, polydipsia, polyuria, weight loss
🏥 ICD-10: E11 - Type 2 diabetes mellitus
💊 藥物: Metformin 500mg 2次/日

📄 SOAP:
```
S - Subjective:  
Mr. Li reports increased thirst and frequent urination for 3 months. Random blood sugar 280 mg/dL. No family history of diabetes.

O - Objective:  
BMI 28. Random blood glucose 280 mg/dL.

A - Assessment:  
Type 2 diabetes mellitus (E11)

P - Plan:  
1. Start Metformin 500mg twice daily
2. Dietary counseling
3. Blood glucose monitoring
4. Follow-up in 4 weeks
```

---

### 傷口護理 (wound_care.wav)

#### qwen2.5:7b (CPU) - 節錄

📋 症狀: wound, infection, redness, swelling, pain
🏥 ICD-10: T14.1 - Open wound

📄 SOAP:
```
S - Subjective:  
Patient reports leg wound for 5 days with increasing redness and swelling.

O - Objective:  
Wound 2cm on left leg, red edges, some discharge.

A - Assessment:  
Infected wound, possible cellulitis.

P - Plan:  
1. Wound cleaning and dressing
2. Oral antibiotics
3. Tetanus prophylaxis if needed
```

---

### 呼吸道 (respiratory.wav)

#### qwen2.5:7b (CPU) - 節錄

📋 症狀: cough, phlegm, wheeze, shortness of breath
🏥 ICD-10: J44.9 - COPD | R05 - Cough

📄 SOAP:
```
S - Subjective:  
Patient reports chronic cough with white sputum for 6 months. Shortness of breath on exertion. 20-year smoking history.

O - Objective:  
Diminished breath sounds bilaterally. Wheezing noted.

A - Assessment:  
Chronic obstructive pulmonary disease (J44.9)

P - Plan:  
1. Pulmonary function tests
2. Bronchodilator therapy
3. Smoking cessation counseling
4. Influenza vaccination
```

---

### 醫囑 (drug_order.wav)

#### qwen2.5:7b (CPU) - 節錄

📋 症狀: medication, prescription
🏥 ICD-10: Z76.5 - Prescription

📄 SOAP:
```
S - Subjective:  
Patient requests refill of blood pressure medication.

O - Objective:  
BP 135/85 mmHg

A - Assessment:  
Hypertension - controlled on current medication

P - Plan:  
1. Continue current medication
2. Recheck BP in 3 months
3. Lifestyle modification
```

---

### 手術記錄 (surgery_record.wav)

#### qwen2.5:7b (CPU) - 節錄

📋 症狀: surgery, laparoscopy, gallbladder
🏥 ICD-10: ICD-10: 51.22 - Laparoscopic cholecystectomy

📄 SOAP:
```
S - Subjective:  
Patient scheduled for laparoscopic cholecystectomy due to gallstones.

O - Objective:  
Pre-op diagnosis: Gallstone disease. No contraindications to surgery.

A - Assessment:  
Cholecystitis with gallstones

P - Plan:  
1. Laparoscopic cholecystectomy
2. Post-op monitoring
3. Low-fat diet
```

---

### 醫病對話 (doctor_patient.wav)

#### qwen2.5:7b (CPU) - 節錄

📋 症狀: fatigue, palpitation, sleep, stress
🏥 ICD-10: R53.83 - Other fatigue | R00.2 - Palpitations

📄 SOAP:
```
S - Subjective:  
35-year-old female with fatigue and poor sleep for 1 month. Work busy with overtime. Occasional palpitations and hand tremors.

O - Objective:  
BP 120/80, HR 76. No thyroid enlargement.

A - Assessment:  
Fatigue and palpitations, possibly stress-related. Rule out hypothyroidism.

P - Plan:  
1. Thyroid function tests (TSH, Free T4)
2. Stress management
3. Follow-up in 1 week
```

---

## 模型平均效能總結

| 模型 | CPU 平均時間 | 推薦度 |
|------|-------------|--------|
| qwen2.5:7b | 9.6 秒 | ⭐⭐⭐ 最佳 |
| qwen2.5:3b | 15.3 秒 | ⭐⭐ 推薦 |
| qwen3.5:4b | 63.7 秒 | ⭐ 不推薦 CPU |
| qwen3.5:9b | 83.1 秒 | ⭐ 不推薦 CPU |

---

## Windows 部署建議

### 推薦模型
- **qwen2.5:7b** - 最佳選擇 (4.7GB, ~10秒/請求)
- **qwen2.5:3b** - 輕量選擇 (1.9GB, ~15秒/請求)

### 部署方式
1. 使用 Ollama 外置 (穩定)
2. 或 llama.cpp CPU 模式 (需解決 GGUF 載入問題)

---

*Generated by SoapVoice comparison script*
*測試時間: 2026-03-27*