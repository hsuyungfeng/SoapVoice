"""
SoapVoice 完整 Pipeline - 整合症狀提取、ICD-10、醫囑、藥物建議

Pipeline:
音頻 → Whisper → 症狀提取 → ICD-10 → 醫囑建議 → 藥物建議 → 完整 SOAP
"""

import time
import requests
from typing import Dict, Any, List
from dataclasses import dataclass
from faster_whisper import WhisperModel
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


class ExtendedSoapVoiceEngine:
    """擴展版 SoapVoice 引擎"""

    def __init__(
        self,
        whisper_model: str = "medium",
        llm_model: str = "qwen2.5:14b",
        compute_mode: str = "cpu",
    ):
        self.whisper_model = whisper_model
        self.llm_model = llm_model
        self.compute_mode = compute_mode
        self._whisper = None
        self._icd_classifier = None
        self._term_mapper = None

    def _init_models(self):
        """初始化模型"""
        if self._whisper is None:
            device = "cuda" if self.compute_mode == "gpu" else "cpu"
            compute = "int8_float16" if self.compute_mode == "gpu" else "int8"
            self._whisper = WhisperModel(self.whisper_model, device=device, compute_type=compute)
            self._icd_classifier, self._term_mapper = load_nlp_modules()

    def transcribe(self, audio_path: str) -> str:
        """語音轉文字"""
        self._init_models()
        segments, _ = self._whisper.transcribe(audio_path, language="zh")
        return "".join([s.text for s in segments])

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
            "R06.02": ["心電圖檢查", "胸部X光", "氧气治疗"],
            "R07.89": ["心電圖", "血壓監測", "心臟酶檢查"],
            "J06.9": ["退燒藥物", "多休息", "門診追蹤"],
        }

        for code in icd10_codes:
            if code in icd_to_order:
                orders.extend(icd_to_order[code])

        # 去重
        return list(set(orders))[:5]

    def get_drug_recommendations(
        self, symptoms: List[str], icd10_codes: List[str]
    ) -> List[Dict[str, str]]:
        """根據症狀和 ICD-10 獲取藥物建議"""
        drugs = []

        # 簡單的症狀對應藥物（實際應從資料庫查詢）
        symptom_drugs = {
            "咳嗽": {"name": "咳特靈", "dosage": "1# 3次/日", "category": "止咳"},
            "胸悶": {"name": "硝酸甘油", "dosage": "舌下含服", "category": "心臟"},
            "發燒": {"name": "普拿疼", "dosage": "500mg 3次/日", "category": "退燒"},
            "頭痛": {"name": "布洛芬", "dosage": "400mg 2次/日", "category": "止痛"},
            "喉嚨痛": {"name": "含片", "dosage": "每日數次", "category": "局部"},
        }

        for symptom in symptoms:
            if symptom in symptom_drugs:
                drugs.append(symptom_drugs[symptom])

        return drugs[:5]

    def generate_extended_soap(
        self,
        transcript: str,
        symptoms: List[str],
        icd10_codes: List[Dict],
        medical_orders: List[str],
        drug_recommendations: List[Dict],
    ) -> Dict[str, str]:
        """生成擴展 SOAP"""

        icd_list = ", ".join([f"{i['code']}: {i['description']}" for i in icd10_codes[:3]])
        orders = ", ".join(medical_orders) if medical_orders else "無"
        drugs = (
            ", ".join([f"{d['name']}({d['dosage']})" for d in drug_recommendations])
            if drug_recommendations
            else "無"
        )

        prompt_en = f"""Create a medical SOAP note in English with the following information:

Transcript: {transcript}
ICD-10 Codes: {icd_list}
Recommended Medical Orders: {orders}
Drug Recommendations: {drugs}

Format:
S - Subjective:
O - Objective: 
A - Assessment:
P - Plan: (include medical orders and drug recommendations)
"""

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": self.llm_model,
                "prompt": prompt_en,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 512},
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
                "options": {"temperature": 0.3, "num_predict": 512},
            },
        )

        soap_zh = response_zh.json().get("response", transcript)

        return {"en": soap_en, "zh": soap_zh}

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
            soap_en=soap_results["en"],
            soap_zh=soap_results["zh"],
            processing_time=processing_time,
        )


def demo():
    """演示"""
    engine = ExtendedSoapVoiceEngine(whisper_model="medium", llm_model="qwen2.5:14b")

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
