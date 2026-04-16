"""
SoapVoice 完整 Pipeline - 整合症狀提取、ICD-10、醫囑、藥物建議

Pipeline:
音頻 → Whisper → 症狀提取 → ICD-10 → 醫囑建議 → 藥物建議 → 完整 SOAP
"""

import time
import requests
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import importlib.util


# 載入 NLP 模組
def load_nlp_modules():
    """載入 NLP 模組"""
    icd_spec = importlib.util.spec_from_file_location("icd10", "src/nlp/icd10_classifier.py")
    icd10 = importlib.util.module_from_spec(icd_spec)
    icd_spec.loader.exec_module(icd10)

    term_spec = importlib.util.spec_from_file_location("term", "src/nlp/terminology_mapper.py")
    term_mapper = importlib.util.module_from_spec(term_spec)
    term_spec.loader.exec_module(term_mapper)

    return icd10.ICD10Classifier(), term_mapper.MedicalTerminologyMapper()


@dataclass
class ExtendedSOAPResult:
    """擴展 SOAP 結果"""

    transcript: str
    symptoms: List[str]
    icd10_codes: List[Dict[str, Any]]
    medical_orders: List[str]
    drug_recommendations: List[Dict[str, str]]
    soap_en: str
    soap_zh: str
    processing_time: float


# 載入 ASR 工廠
def load_asr_factory():
    """載入 ASR 工廠"""
    import sys
    from pathlib import Path
    
    # 確保 src 正在 sys.path 中
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        
    from src.asr.asr_factory import ASRBackendFactory
    return ASRBackendFactory


class ExtendedSoapVoiceEngine:
    """擴展版 SoapVoice 引擎"""

    def __init__(
        self,
        whisper_model: Optional[str] = None,
        llm_model: Optional[str] = None,
        compute_mode: str = "cpu",
    ):
        self.whisper_model = whisper_model or os.getenv("ASR_MODEL", "distil-large-v3")
        self.llm_model = llm_model or os.getenv("LLM_MODEL", "qwen2.5:7b")
        self.compute_mode = compute_mode
        self._whisper = None
        self._icd_classifier = None
        self._term_mapper = None

    def initialize(self):
        """顯式初始化所有模型 (預加載)"""
        print(f"🚀 正在初始化 ExtendedSoapVoiceEngine (模型: {self.whisper_model})...")
        self._init_models()
        print("✅ ExtendedSoapVoiceEngine 初始化完成")

    def _init_models(self):
        """內部初始化模型"""
        if self._whisper is None:
            # 從環境變數讀取計算類型
            compute_type = os.getenv("ASR_COMPUTE_TYPE", "int8")
            # 使用 ASR 工廠進行初始化 (支援模型快取)
            factory = load_asr_factory()
            self._whisper = factory.create_backend(
                backend="whisper",
                model_id=self.whisper_model,
                device=self.compute_mode,
                compute_type=compute_type,
                download_root="models/whisper"
            )
            self._icd_classifier, self._term_mapper = load_nlp_modules()

    def transcribe(self, audio_path: str) -> str:
        """語音轉文字"""
        self._init_models()
        result = self._whisper.transcribe(audio_path, language="zh")
        return result.get("text", "")

    def extract_symptoms(self, text: str) -> List[str]:
        """從文字提取症狀"""
        self._init_models()
        # 使用 terminology_mapper
        _, mappings = self._term_mapper.map_text(text)
        symptoms = [m.standard for m in mappings]

        # 額外提取常見症狀關鍵字
        common_symptoms = [
            "咳嗽",
            "胸悶",
            "呼吸困難",
            "發燒",
            "頭痛",
            "喉嚨痛",
            "腹痛",
            "腹瀉",
            "嘔吐",
        ]
        for s in common_symptoms:
            if s in text and s not in symptoms:
                symptoms.append(s)

        return symptoms

    def classify_icd10(self, text: str) -> List[Dict[str, Any]]:
        """ICD-10 分類"""
        self._init_models()
        matches = self._icd_classifier.classify(text)
        return [
            {"code": m.code, "description": m.description, "confidence": m.confidence}
            for m in matches
        ]

    def get_medical_orders(self, symptoms: List[str], icd10_codes: List[str]) -> List[str]:
        """根據症狀和 ICD-10 獲取醫囑建議"""
        self._init_models()
        orders = []

        # 根據 ICD-10 代碼提供基本醫囑
        icd_to_order = {
            "R05": ["止咳藥物", "祛痰劑", "多喝水"],
            "R06.02": ["心電圖檢查", "胸部X光", "氧氣治療"],
            "R07.89": ["心電圖", "血壓監測", "心臟酶檢查"],
            "R07.9": ["心電圖", "心臟超音波", "生化檢查"],
            "J06.9": ["退燒藥物", "多休息", "門診追蹤"],
            "R51": ["休息", "避免強光", "血壓監測"],
            "R42": ["臥床休息", "避免突然改變體位", "前庭功能檢查"],
            "R11.0": ["暫時禁食", "少量多次飲水", "止吐藥物"],
            "R11.2": ["暫時禁食", "靜脈補液", "止吐藥物"],
            "R10.9": ["腹部超音波", "血常規檢查", "暫時流質飲食"],
            "R19.7": ["補充電解質", "益生菌", "清淡飲食"],
            "I10": ["每日量血壓", "低鹽飲食", "按時服藥"],
            "K29.7": ["胃鏡檢查建議", "清淡飲食", "制酸劑"],
            "R58": ["傷口加壓止血", "傷口處理", "破傷風疫苗評估"],
        }

        for code in icd10_codes:
            if code in icd_to_order:
                orders.extend(icd_to_order[code])

        # 根據症狀提供額外醫囑
        symptom_to_order = {
            "headache": ["休息", "避免壓力"],
            "dizziness": ["避免開車", "休息"],
            "abdominal pain": ["禁食生冷", "熱敷腹部"],
            "diarrhea": ["補水", "避免油膩"],
            "bleeding": ["傷口清潔", "保持乾燥"],
        }

        for symptom in symptoms:
            s_lower = symptom.lower()
            if s_lower in symptom_to_order:
                orders.extend(symptom_to_order[s_lower])

        # 去重
        return list(set(orders))[:8]

    def get_drug_recommendations(
        self, symptoms: List[str], icd10_codes: List[str]
    ) -> List[Dict[str, str]]:
        """根據症狀和 ICD-10 獲取藥物建議"""
        drugs = []

        # 簡單的症狀對應藥物（實際應從資料庫查詢）
        symptom_drugs = {
            "咳嗽": {"name": "咳特靈", "dosage": "1# 3次/日", "category": "止咳"},
            "cough": {"name": "Cough Syrup", "dosage": "10ml 3次/日", "category": "Antitussive"},
            "胸悶": {"name": "硝酸甘油", "dosage": "舌下含服", "category": "心臟"},
            "chest tightness": {"name": "Nitroglycerin", "dosage": "SL PRN", "category": "Cardiac"},
            "發燒": {"name": "普拿疼", "dosage": "500mg 3次/日", "category": "退燒"},
            "fever": {"name": "Paracetamol", "dosage": "500mg TID", "category": "Antipyretic"},
            "頭痛": {"name": "布洛芬", "dosage": "400mg 2次/日", "category": "止痛"},
            "headache": {"name": "Ibuprofen", "dosage": "400mg BID", "category": "Analgesic"},
            "喉嚨痛": {"name": "含片", "dosage": "每日數次", "category": "局部"},
            "sore throat": {"name": "Throat Lozenge", "dosage": "PRN", "category": "Local"},
            "頭暈": {"name": "止暈藥", "dosage": "1# 3次/日", "category": "止暈"},
            "dizziness": {"name": "Meclizine", "dosage": "25mg TID", "category": "Antivertigo"},
            "vertigo": {"name": "Meclizine", "dosage": "25mg TID", "category": "Antivertigo"},
            "嘔吐": {"name": "止吐藥", "dosage": "1# 3次/日", "category": "止吐"},
            "vomiting": {"name": "Domperidone", "dosage": "10mg TID", "category": "Antiemetic"},
            "nausea": {"name": "Domperidone", "dosage": "10mg TID", "category": "Antiemetic"},
            "腹痛": {"name": "補斯可胖", "dosage": "1# 3次/日", "category": "解痙"},
            "abdominal pain": {"name": "Buscopan", "dosage": "10mg TID", "category": "Antispasmodic"},
            "腹瀉": {"name": "舒腹達", "dosage": "1包 3次/日", "category": "止瀉"},
            "diarrhea": {"name": "Smecta", "dosage": "1 sac TID", "category": "Antidiarrheal"},
            "high blood pressure": {"name": "Amlodipine", "dosage": "5mg QD", "category": "Antihypertensive"},
            "gastroenteritis": {"name": "Gastrogel", "dosage": "10ml TID", "category": "Antacid"},
        }

        for symptom in symptoms:
            s_lower = symptom.lower()
            if s_lower in symptom_drugs:
                drugs.append(symptom_drugs[s_lower])
            elif symptom in symptom_drugs:
                drugs.append(symptom_drugs[symptom])

        return drugs[:5]


    def generate_extended_soap(
        self,
        transcript: str,
        symptoms: List[str],
        icd10_codes: List[Dict],
        medical_orders: List[str],
        drug_recommendations: List[Dict],
        output_lang: str = "en",
    ) -> Dict[str, str]:
        """生成擴展 SOAP"""

        icd_list = ", ".join([f"{i['code']}: {i['description']}" for i in icd10_codes[:3]])
        orders = ", ".join(medical_orders) if medical_orders else "無"
        drugs = (
            ", ".join([f"{d['name']}({d['dosage']})" for d in drug_recommendations])
            if drug_recommendations
            else "無"
        )

        prompt_en = f"""Create a medical SOAP note in ENGLISH ONLY. Do not write in Chinese or any other language.

Transcript (Chinese): {transcript}
ICD-10 Codes: {icd_list}
Recommended Medical Orders: {orders}
Drug Recommendations: {drugs}

Write the SOAP note entirely in English with this format:
S - Subjective:
O - Objective: 
A - Assessment:
P - Plan:
"""

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": self.llm_model,
                "prompt": prompt_en,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 2048, "device": "cpu"},
            },
        )

        soap_en = response.json().get("response", "No response")

        # 中文翻譯
        prompt_zh = f"""翻譯以下文字為繁體中文，只輸出翻譯結果：

{soap_en}
"""

        response_zh = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": self.llm_model,
                "prompt": prompt_zh,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 2048, "device": "cpu"},
            },
        )

        soap_zh = response_zh.json().get("response", transcript)

        # 解析 SOAP 各欄位
        soap_dict = {
            "subjective": "",
            "objective": "",
            "assessment": "",
            "plan": "",
            "medical_orders": medical_orders,
            "drug_recommendations": drug_recommendations,
            "raw_en": soap_en,
            "raw_zh": soap_zh,
        }

        # 嘗試解析英文版
        lines = soap_en.split("\n")
        current_section = None
        for line in lines:
            line = line.strip()
            if line.lower().startswith("s - subjective:") or line.lower().startswith("s:"):
                current_section = "subjective"
                content = line.split(":", 1)[1].strip() if ":" in line else ""
                if content:
                    soap_dict["subjective"] += content + "\n"
            elif line.lower().startswith("o - objective:") or line.lower().startswith("o:"):
                current_section = "objective"
                content = line.split(":", 1)[1].strip() if ":" in line else ""
                if content:
                    soap_dict["objective"] += content + "\n"
            elif line.lower().startswith("a - assessment:") or line.lower().startswith("a:"):
                current_section = "assessment"
                content = line.split(":", 1)[1].strip() if ":" in line else ""
                if content:
                    soap_dict["assessment"] += content + "\n"
            elif line.lower().startswith("p - plan:") or line.lower().startswith("p:"):
                current_section = "plan"
                content = line.split(":", 1)[1].strip() if ":" in line else ""
                if content:
                    soap_dict["plan"] += content + "\n"
            elif current_section and line:
                soap_dict[current_section] += line + "\n"

        # 清理空白
        for key in ["subjective", "objective", "assessment", "plan"]:
            soap_dict[key] = soap_dict[key].strip()

        return soap_dict

    def process(self, audio_path: str) -> ExtendedSOAPResult:
        """完整處理流程"""
        start_time = time.time()

        # Step 1: 轉錄
        print("📝 Step 1: 語音轉文字...")
        transcript = self.transcribe(audio_path)
        print(f"   轉錄結果: {transcript}")

        # Step 2: 症狀提取
        print("🔍 Step 2: 症狀提取...")
        symptoms = self.extract_symptoms(transcript)
        print(f"   症狀: {symptoms}")

        # Step 3: ICD-10 分類
        print("🏥 Step 3: ICD-10 分類...")
        icd10_codes = self.classify_icd10(transcript)
        print(f"   ICD-10: {[c['code'] for c in icd10_codes]}")

        # Step 4: 醫囑建議
        print("📋 Step 4: 醫囑建議...")
        icd_codes = [c["code"] for c in icd10_codes]
        medical_orders = self.get_medical_orders(symptoms, icd_codes)
        print(f"   醫囑: {medical_orders}")

        # Step 5: 藥物建議
        print("💊 Step 5: 藥物建議...")
        drug_recommendations = self.get_drug_recommendations(symptoms, icd_codes)
        print(f"   藥物: {[d['name'] for d in drug_recommendations]}")

        # Step 6: 生成 SOAP
        print("📄 Step 6: 生成 SOAP 病歷...")
        soap_results = self.generate_extended_soap(
            transcript, symptoms, icd10_codes, medical_orders, drug_recommendations
        )

        processing_time = time.time() - start_time

        return ExtendedSOAPResult(
            transcript=transcript,
            symptoms=symptoms,
            icd10_codes=icd10_codes,
            medical_orders=medical_orders,
            drug_recommendations=drug_recommendations,
            soap_en=soap_results["raw_en"],
            soap_zh=soap_results["raw_zh"],
            processing_time=processing_time,
        )


def demo():
    """演示"""
    engine = ExtendedSoapVoiceEngine(whisper_model="medium", llm_model="qwen2.5:7b")

    audio_file = "tests/fixtures/sample_zh.wav"

    print("=" * 60)
    print("Extended SoapVoice Pipeline Test")
    print("=" * 60)

    result = engine.process(audio_file)

    print("\n" + "=" * 60)
    print("📋 完整結果")
    print("=" * 60)

    print(f"\n⏱️ 處理時間: {result.processing_time:.2f}s")

    print("\n📝 中文逐字稿:")
    print(result.transcript)

    print("\n🔍 提取的症狀:")
    print(result.symptoms)

    print("\n🏥 ICD-10 分類:")
    for icd in result.icd10_codes:
        print(f"   {icd['code']}: {icd['description']} ({icd['confidence']:.0%})")

    print("\n📋 醫囑建議:")
    for order in result.medical_orders:
        print(f"   - {order}")

    print("\n💊 藥物建議:")
    for drug in result.drug_recommendations:
        print(f"   - {drug['name']} ({drug['dosage']}) - {drug['category']}")

    print("\n" + "=" * 60)
    print("📄 English SOAP Note")
    print("=" * 60)
    print(result.soap_en)


if __name__ == "__main__":
    demo()
