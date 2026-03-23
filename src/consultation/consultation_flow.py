"""
門診諮詢流程核心模組

整合語音轉文字、資料庫查詢、LLM 生成的一站式門診諮詢流程
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

from src.asr.stream_transcriber import StreamTranscriber
from src.asr.whisper_model import WhisperModel
from src.db.local_database import LocalDatabase
from src.db.atc_classification import get_atc_by_symptom
from src.soap.soap_generator import SOAPGenerator, SOAPConfig


logger = logging.getLogger(__name__)


class ConsultationState(Enum):
    """諮詢狀態"""

    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ConsultationConfig:
    """諮詢流程配置"""

    max_duration_seconds: int = 600  # 10 分鐘
    whisper_model_size: str = "medium"
    whisper_language: str = "zh"
    llm_model: str = "qwen3.5:9b"
    llm_api_base: str = "http://localhost:11434"
    max_tokens: int = 1024
    temperature: float = 0.3
    save_recordings: bool = True
    recordings_dir: Path = field(default_factory=lambda: Path("data/recordings"))
    db_path: Path = field(default_factory=lambda: Path("data/local_db/medical.db"))


@dataclass
class SessionSummary:
    """會話摘要"""

    session_id: str
    patient_context: Dict[str, Any]
    transcript: str
    segments: List[Dict[str, Any]]
    duration_seconds: float
    icd10_codes: List[Dict[str, str]]
    drug_recommendations: List[Dict[str, str]]
    medical_orders: List[Dict[str, str]]
    created_at: datetime


@dataclass
class SearchResult:
    """搜尋結果"""

    category: str  # "icd10", "drug", "order"
    code: str
    name: str
    description: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsultationResult:
    """諮詢結果"""

    session_id: str
    soap: Dict[str, str]
    session_summary: SessionSummary
    metadata: Dict[str, Any]
    processing_time_ms: float


class ConsultationFlow:
    """門診諮詢流程管理器

    整合以下元件：
    - StreamTranscriber：即時語音轉文字
    - LocalDatabase：本地 ICD-10、藥品、醫療服務查詢
    - SOAPGenerator：生成 SOAP 病歷
    """

    def __init__(self, config: Optional[ConsultationConfig] = None):
        """初始化諮詢流程

        Args:
            config: 諮詢流程配置
        """
        self.config = config or ConsultationConfig()
        self._state = ConsultationState.IDLE
        self._session_id: Optional[str] = None
        self._transcriber: Optional[StreamTranscriber] = None
        self._whisper_model = None
        self._db: Optional[LocalDatabase] = None
        self._soap_generator: Optional[SOAPGenerator] = None
        self._patient_context: Dict[str, Any] = {}
        self._transcript_parts: List[str] = []
        self._segments: List[Dict[str, Any]] = []
        self._start_time: Optional[float] = None
        self._audio_chunks: List[bytes] = []
        self._on_transcript_update: Optional[Callable[[str], None]] = None
        self._search_cache: Dict[str, List[SearchResult]] = {}

        # 確保錄音目錄存在
        if self.config.save_recordings:
            self.config.recordings_dir.mkdir(parents=True, exist_ok=True)

    @property
    def state(self) -> ConsultationState:
        """取得當前狀態"""
        return self._state

    @property
    def session_id(self) -> Optional[str]:
        """取得當前會話 ID"""
        return self._session_id

    @property
    def is_recording(self) -> bool:
        """是否正在錄音"""
        return self._state == ConsultationState.RECORDING

    def set_patient_context(self, context: Dict[str, Any]) -> None:
        """設定病患背景資訊

        Args:
            context: 病患背景（年齡、性別、主訴等）
        """
        self._patient_context = context
        logger.info(f"病患背景已設定: {context}")

    def set_transcript_callback(self, callback: Callable[[str], None]) -> None:
        """設定轉文字更新回調

        Args:
            callback: 每次有新文字時的回調函式
        """
        self._on_transcript_update = callback

    def _initialize_components(self) -> None:
        """初始化各元件"""
        # 初始化 Whisper 模型
        if self._whisper_model is None:
            logger.info("初始化 Whisper 模型...")
            self._whisper_model = WhisperModel(
                model_id=self.config.whisper_model_size,
                device="auto",
                compute_type="auto",
            )
            self._transcriber = StreamTranscriber(
                whisper_model=self._whisper_model,
                language=self.config.whisper_language,
                task="transcribe",
            )
            logger.info("Whisper 模型初始化完成")

        # 初始化資料庫
        if self._db is None:
            logger.info("初始化本地資料庫...")
            self._db = LocalDatabase(self.config.db_path)
            logger.info("本地資料庫初始化完成")

        # 初始化 SOAP 生成器（延遲初始化 LLM）
        if self._soap_generator is None:
            logger.info("初始化 SOAP 生成器...")
            soap_config = SOAPConfig(
                model_id=self.config.llm_model,
                api_base=self.config.llm_api_base,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
            self._soap_generator = SOAPGenerator(soap_config)
            logger.info("SOAP 生成器初始化完成")

    def start_consultation(self) -> Dict[str, Any]:
        """開始新的諮詢會話

        Returns:
            會話資訊字典
        """
        if self._state == ConsultationState.RECORDING:
            raise RuntimeError("諮詢會話已在進行中")

        self._initialize_components()

        # 產生新的會話 ID
        self._session_id = str(uuid.uuid4())[:8]
        self._transcript_parts = []
        self._segments = []
        self._audio_chunks = []
        self._search_cache = {}
        self._start_time = time.time()

        # 啟動轉錄器
        if self._transcriber:
            self._transcriber.start_stream()

        self._state = ConsultationState.RECORDING
        logger.info(f"諮詢會話已開始: {self._session_id}")

        return {
            "session_id": self._session_id,
            "status": "started",
            "message": "諮詢會話已開始，請開始說話",
            "patient_context": self._patient_context,
        }

    def process_audio_chunk(self, audio_chunk: bytes) -> Dict[str, Any]:
        """處理音頻塊

        Args:
            audio_chunk: 音頻數據（bytes）

        Returns:
            處理結果字典
        """
        if self._state != ConsultationState.RECORDING:
            return {
                "status": "not_recording",
                "text": "",
                "is_final": False,
            }

        # 保存音頻塊
        self._audio_chunks.append(audio_chunk)

        # 檢查時長限制
        elapsed = time.time() - self._start_time if self._start_time else 0
        if elapsed > self.config.max_duration_seconds:
            return self.end_consultation()

        # 處理音頻
        if self._transcriber:
            result = self._transcriber.process_chunk(audio_chunk)
            if result.get("text"):
                current_text = result["text"]
                self._transcript_parts.append(current_text)

                # 觸發回調
                if self._on_transcript_update:
                    self._on_transcript_update(current_text)

                # 嘗試即時搜尋
                self._realtime_search(current_text)

                return {
                    "status": "recording",
                    "text": current_text,
                    "is_final": False,
                    "elapsed_seconds": round(elapsed, 1),
                    "suggestions": self._get_search_suggestions(),
                }

        return {
            "status": "recording",
            "text": "",
            "is_final": False,
            "elapsed_seconds": round(elapsed, 1),
        }

    def pause_consultation(self) -> Dict[str, Any]:
        """暫停諮詢會話"""
        if self._state != ConsultationState.RECORDING:
            raise RuntimeError("沒有正在進行的諮詢會話")

        self._state = ConsultationState.PAUSED
        elapsed = time.time() - self._start_time if self._start_time else 0

        logger.info(f"諮詢會話已暫停: {self._session_id}, 已錄製 {elapsed:.1f} 秒")

        return {
            "status": "paused",
            "session_id": self._session_id,
            "elapsed_seconds": round(elapsed, 1),
            "transcript_preview": " ".join(self._transcript_parts[-3:])
            if self._transcript_parts
            else "",
        }

    def resume_consultation(self) -> Dict[str, Any]:
        """恢復諮詢會話"""
        if self._state != ConsultationState.PAUSED:
            raise RuntimeError("沒有暫停的諮詢會話")

        self._state = ConsultationState.RECORDING
        logger.info(f"諮詢會話已恢復: {self._session_id}")

        return {
            "status": "resumed",
            "session_id": self._session_id,
            "message": "請繼續說話",
        }

    def end_consultation(self) -> Dict[str, Any]:
        """結束諮詢會話

        Returns:
            結束資訊字典
        """
        if self._state not in (ConsultationState.RECORDING, ConsultationState.PAUSED):
            raise RuntimeError("沒有正在進行或已暫停的諮詢會話")

        self._state = ConsultationState.PROCESSING
        elapsed = time.time() - self._start_time if self._start_time else 0

        # 結束轉錄
        if self._transcriber:
            final_result = self._transcriber.end_stream()
            if final_result.get("text"):
                self._transcript_parts = [final_result["text"]]
            if final_result.get("segments"):
                self._segments = final_result["segments"]

        # 保存錄音
        if self.config.save_recordings and self._audio_chunks:
            self._save_audio()

        logger.info(f"諮詢會話已結束: {self._session_id}, 總時長 {elapsed:.1f} 秒")

        return {
            "status": "ended",
            "session_id": self._session_id,
            "elapsed_seconds": round(elapsed, 1),
            "transcript": " ".join(self._transcript_parts),
            "segments_count": len(self._segments),
            "message": "錄音已結束，正在處理 SOAP 病歷...",
        }

    def generate_soap(self) -> ConsultationResult:
        """生成 SOAP 病歷

        Returns:
            完整的諮詢結果
        """
        if self._state != ConsultationState.PROCESSING:
            raise RuntimeError("請先結束諮詢會話")

        start_time = time.time()
        transcript = " ".join(self._transcript_parts)
        elapsed = time.time() - self._start_time if self._start_time else 0

        # 收集 ICD-10、藥品、醫療服務建議
        icd10_codes = self._extract_icd10_codes(transcript)
        drug_recommendations = self._extract_drug_recommendations(transcript)
        medical_orders = self._extract_medical_orders(transcript)

        # 生成 SOAP
        try:
            soap_dict = self._soap_generator.generate(
                transcript=transcript,
                patient_context=self._patient_context,
            )
        except Exception as e:
            logger.error(f"SOAP 生成失敗: {e}")
            soap_dict = {
                "subjective": transcript[:500],
                "objective": "（LLM 生成失敗）",
                "assessment": "（請醫師自行評估）",
                "plan": "（請醫師自行開立）",
                "conversation_summary": transcript[:200] if transcript else "",
            }

        # 建立會話摘要
        session_summary = SessionSummary(
            session_id=self._session_id or "",
            patient_context=self._patient_context.copy(),
            transcript=transcript,
            segments=self._segments.copy(),
            duration_seconds=elapsed,
            icd10_codes=icd10_codes,
            drug_recommendations=drug_recommendations,
            medical_orders=medical_orders,
            created_at=datetime.now(),
        )

        processing_time = (time.time() - start_time) * 1000

        result = ConsultationResult(
            session_id=self._session_id or "",
            soap={
                "subjective": soap_dict.get("subjective", ""),
                "objective": soap_dict.get("objective", ""),
                "assessment": soap_dict.get("assessment", ""),
                "plan": soap_dict.get("plan", ""),
                "conversation_summary": soap_dict.get("conversation_summary", ""),
            },
            session_summary=session_summary,
            metadata={
                "elapsed_seconds": round(elapsed, 1),
                "segments_count": len(self._segments),
                "icd10_count": len(icd10_codes),
                "drug_count": len(drug_recommendations),
                "order_count": len(medical_orders),
                "normalized_terms": soap_dict.get("normalized_terms", []),
            },
            processing_time_ms=round(processing_time, 2),
        )

        self._state = ConsultationState.COMPLETED
        logger.info(f"SOAP 生成完成: {self._session_id}, 耗時 {processing_time:.0f}ms")

        return result

    def _realtime_search(self, text: str) -> None:
        """根據目前文字進行即時搜尋

        Args:
            text: 目前轉錄文字
        """
        if not self._db:
            return

        # 根據症狀關鍵字搜尋
        symptoms = self._extract_symptoms(text)
        for symptom in symptoms:
            if symptom not in self._search_cache:
                results = self._search_by_symptom(symptom)
                self._search_cache[symptom] = results

    def _extract_symptoms(self, text: str) -> List[str]:
        """從文字中提取症狀關鍵字

        Args:
            text: 文字

        Returns:
            症狀列表
        """
        symptom_keywords = [
            "頭痛",
            "頭暈",
            "發燒",
            "咳嗽",
            "喉嚨痛",
            "鼻塞",
            "流鼻水",
            "胸悶",
            "胸痛",
            "腹痛",
            "腹瀉",
            "便秘",
            "嘔吐",
            "胃痛",
            "關節痛",
            "肌肉痛",
            "背痛",
            "皮膚癢",
            "濕疹",
            "過敏",
            "失眠",
            "焦慮",
            "血壓高",
            "血糖高",
        ]

        found = []
        for symptom in symptom_keywords:
            if symptom in text:
                found.append(symptom)
        return found

    def _search_by_symptom(self, symptom: str) -> List[SearchResult]:
        """根據症狀搜尋資料庫

        Args:
            symptom: 症狀關鍵字

        Returns:
            搜尋結果列表
        """
        results = []

        # 取得可能的 ATC 分類
        atc_codes = get_atc_by_symptom(symptom)

        # 搜尋 ICD-10
        icd10_results = self._db.search_icd10(symptom, limit=3)
        for r in icd10_results:
            results.append(
                SearchResult(
                    category="icd10",
                    code=r.code,
                    name=r.name_cn,
                    description=f"{r.name_en} ({r.category})",
                )
            )

        # 搜尋藥品（根據 ATC 分類）
        for atc_code in atc_codes[:2]:
            drug_results = self._db.search_drugs_by_atc_class(atc_code, limit=3)
            for r in drug_results:
                results.append(
                    SearchResult(
                        category="drug",
                        code=r.drug_code,
                        name=r.drug_name_cn,
                        description=f"ATC: {r.atc_code} | {r.drug_class}",
                        metadata={"atc_code": r.atc_code, "price": r.payment_price},
                    )
                )

        return results

    def _get_search_suggestions(self) -> Dict[str, List[Dict[str, Any]]]:
        """取得目前搜尋建議

        Returns:
            依分類的搜尋建議
        """
        suggestions: Dict[str, List[Dict[str, Any]]] = {
            "icd10": [],
            "drug": [],
            "order": [],
        }

        for symptom, results in self._search_cache.items():
            for r in results:
                if r.category == "icd10":
                    suggestions["icd10"].append(
                        {
                            "code": r.code,
                            "name": r.name,
                            "symptom": symptom,
                        }
                    )
                elif r.category == "drug":
                    suggestions["drug"].append(
                        {
                            "code": r.code,
                            "name": r.name,
                            "atc_code": r.metadata.get("atc_code", ""),
                            "price": r.metadata.get("price", 0),
                            "symptom": symptom,
                        }
                    )

        # 限制每類建議數量
        for key in suggestions:
            suggestions[key] = suggestions[key][:5]

        return suggestions

    def _extract_icd10_codes(self, transcript: str) -> List[Dict[str, str]]:
        """從文字中提取 ICD-10 建議

        Args:
            transcript: 對話文字

        Returns:
            ICD-10 建議列表
        """
        codes = []
        symptoms = self._extract_symptoms(transcript)
        for symptom in symptoms:
            icd10_results = self._db.search_icd10(symptom, limit=3) if self._db else []
            for r in icd10_results:
                codes.append(
                    {
                        "code": r.code,
                        "name": r.name_cn,
                        "symptom": symptom,
                    }
                )
        return codes[:10]

    def _extract_drug_recommendations(self, transcript: str) -> List[Dict[str, str]]:
        """從文字中提取藥品建議

        Args:
            transcript: 對話文字

        Returns:
            藥品建議列表
        """
        drugs = []
        symptoms = self._extract_symptoms(transcript)
        for symptom in symptoms:
            atc_codes = get_atc_by_symptom(symptom)
            for atc_code in atc_codes[:1]:
                drug_results = (
                    self._db.search_drugs_by_atc_class(atc_code, limit=3) if self._db else []
                )
                for r in drug_results:
                    drugs.append(
                        {
                            "code": r.drug_code,
                            "name": r.drug_name_cn,
                            "atc_code": r.atc_code,
                            "symptom": symptom,
                        }
                    )
        return drugs[:10]

    def _extract_medical_orders(self, transcript: str) -> List[Dict[str, str]]:
        """從文字中提取醫療服務建議

        Args:
            transcript: 對話文字

        Returns:
            醫療服務建議列表
        """
        orders = []
        symptoms = self._extract_symptoms(transcript)
        for symptom in symptoms:
            order_results = self._db.search_medical_orders(symptom, limit=3) if self._db else []
            for r in order_results:
                orders.append(
                    {
                        "code": r.order_code,
                        "name": r.name_cn,
                        "category": r.category,
                        "symptom": symptom,
                    }
                )
        return orders[:10]

    def _save_audio(self) -> Optional[Path]:
        """保存錄音檔案

        Returns:
            保存路徑或 None
        """
        if not self._audio_chunks or not self._session_id:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"consultation_{self._session_id}_{timestamp}.wav"
        filepath = self.config.recordings_dir / filename

        try:
            import wave
            import io

            # 合併音頻塊
            audio_data = b"".join(self._audio_chunks)

            # 轉換為 WAV
            with io.BytesIO(audio_data) as input_io:
                with wave.open(input_io, "rb") as wav_in:
                    params = wav_in.getparams()
                    frames = wav_in.readframes(wav_in.getnframes())

            # 寫入檔案
            with wave.open(str(filepath), "wb") as wav_out:
                wav_out.setparams(params)
                wav_out.writeframes(frames)

            logger.info(f"錄音已保存: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"保存錄音失敗: {e}")
            return None

    def get_current_transcript(self) -> str:
        """取得目前轉錄文字

        Returns:
            目前轉錄文字
        """
        return " ".join(self._transcript_parts)

    def get_realtime_stats(self) -> Dict[str, Any]:
        """取得即時統計資訊

        Returns:
            統計資訊字典
        """
        elapsed = time.time() - self._start_time if self._start_time else 0
        return {
            "state": self._state.value,
            "session_id": self._session_id,
            "elapsed_seconds": round(elapsed, 1),
            "transcript_length": len(" ".join(self._transcript_parts)),
            "segments_count": len(self._segments),
            "audio_chunks": len(self._audio_chunks),
            "search_cache_size": len(self._search_cache),
        }

    def reset(self) -> None:
        """重置諮詢流程"""
        self._state = ConsultationState.IDLE
        self._session_id = None
        self._transcript_parts = []
        self._segments = []
        self._audio_chunks = []
        self._search_cache = {}
        self._patient_context = {}
        self._start_time = None

        if self._transcriber and self._transcriber.is_streaming:
            try:
                self._transcriber.end_stream()
            except Exception:
                pass

        logger.info("諮詢流程已重置")
