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
        self.whisper_model = whisper_model or os.getenv("ASR_MODEL", "Qwen/Qwen3-ASR-0.6B")
        self.llm_model = llm_model or os.getenv("LLM_MODEL", "qwen2.5:7b")
        self.asr_backend = os.getenv("ASR_BACKEND", "qwen3asr")
        self.compute_mode = compute_mode
        self._whisper = None
        self._icd_classifier = None
        self._term_mapper = None

    def initialize(self):
        """顯式初始化所有模型 (預加載)"""
        backend_name = "Qwen3-ASR" if self.asr_backend == "qwen3asr" else "Whisper"
        print(f"🚀 正在初始化 ExtendedSoapVoiceEngine ({backend_name} 模型: {self.whisper_model})...")
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
                backend=self.asr_backend,
                model_id=self.whisper_model,
                device=self.compute_mode,
                compute_type=compute_type,
                download_root="models/whisper"
            )
            self._icd_classifier, self._term_mapper = load_nlp_modules()

    def transcribe(self, audio_path: str, model: Optional[str] = None, backend: str = "whisper") -> str:
        """語音轉文字"""
        # 如果指定了不同於目前的 ASR 引擎，則重新初始化對應後端
        if model and model != self.whisper_model:
             factory = load_asr_factory()
             compute_type = os.getenv("ASR_COMPUTE_TYPE", "int8")
             current_asr = factory.create_backend(
                backend=backend,
                model_id=model,
                device=self.compute_mode,
                compute_type=compute_type,
                download_root="models/whisper"
             )
        else:
             self._init_models()
             current_asr = self._whisper
        
        result = current_asr.transcribe(audio_path, language="zh")
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
        from src.db.clinical_db import ClinicalDatabase
        db = ClinicalDatabase()
        return db.get_medical_orders(symptoms, icd10_codes)

    def get_drug_recommendations(
        self, symptoms: List[str], icd10_codes: List[str]
    ) -> List[Dict[str, str]]:
        """根據症狀和 ICD-10 獲取藥物建議"""
        from src.db.clinical_db import ClinicalDatabase
        db = ClinicalDatabase()
        return db.get_drug_recommendations(symptoms, icd10_codes)


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
        from src.soap.soap_generator import get_generator
        
        generator = get_generator()
        
        # 使用 SOAPGenerator 進行生成
        result = generator.generate(
            transcript=transcript,
            medical_orders=medical_orders,
            drug_recommendations=drug_recommendations
        )
        
        # 轉換成 API 回應格式
        soap_dict = {
            "subjective": result.get("subjective", ""),
            "objective": result.get("objective", ""),
            "assessment": result.get("assessment", ""),
            "plan": result.get("plan", ""),
            "medical_orders": medical_orders,
            "drug_recommendations": drug_recommendations,
            "en": result.get("raw_response", ""),
            "zh": result.get("conversation_summary", ""),
            "raw_en": result.get("raw_response", ""),
            "raw_zh": result.get("conversation_summary", ""),
        }
        
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
