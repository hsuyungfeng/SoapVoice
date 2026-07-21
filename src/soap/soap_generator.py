"""
SOAP 生成模組

將醫療對話轉換成結構化 SOAP 病歷
"""

import logging
import os
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path

from src.utils.resource_path import get_resource_path
from src.nlp.soap_classifier import SOAPClassifier
from src.nlp.terminology_mapper import MedicalTerminologyMapper, TermMapping
from src.nlp.compliance_guard import ClinicalComplianceGuard

# 引擎選擇：使用 llama.cpp 或 Ollama
USE_LLAMA_CPP = os.getenv("USE_LLAMA_CPP", "false").lower() == "true"

if USE_LLAMA_CPP:
    from src.llm.llama_engine import LlamaEngine as Engine, LlamaConfig as EngineConfig
    from src.llm.llama_engine import initialize_llama_engine as initialize_engine

    logger = logging.getLogger(__name__)
    logger.info("使用 llama.cpp 引擎")
else:
    from src.llm.ollama_engine import OllamaEngine as Engine, ModelConfig as EngineConfig
    from src.llm.ollama_engine import initialize_engine

    logger = logging.getLogger(__name__)
    logger.info("使用 Ollama 引擎")


logger = logging.getLogger(__name__)

# 共用 SOAPClassifier 的關鍵字字典，避免重複定義
SOAP_KEYWORDS = SOAPClassifier.KEYWORDS

# RAG 相關設定
RAG_DB_PATH = Path("data/rag/chroma")
RAG_SQLITE_PATH = Path("data/rag/case_templates.db")


@dataclass
class SOAPConfig:
    """SOAP 生成配置"""

    model_id: str = "qwen3.5:9b"
    api_base: str = "http://localhost:11434"
    max_tokens: int = 1024
    temperature: float = 0.3
    num_ctx: int = int(os.getenv("LLAMA_N_CTX", "4096"))
    max_subjective_length: int = 100  # 字元限制
    enable_rag: bool = True  # 啟用 RAG 病例範本檢索
    rag_top_k: int = 3  # RAG 檢索結果數量
    rag_min_similarity: float = 0.3  # RAG 最小相似度


class SOAPGenerator:
    """SOAP 病歷生成器"""

    def __init__(self, config: Optional[SOAPConfig] = None):
        """初始化 SOAP 生成器"""
        self.config = config or SOAPConfig()
        self._engine: Optional[Engine] = None
        self._mapper: MedicalTerminologyMapper = MedicalTerminologyMapper()
        self._compliance_guard: ClinicalComplianceGuard = ClinicalComplianceGuard()

        # RAG 系統初始化
        self._rag_client = None
        self._rag_collection = None
        self._embedding_model = None
        if self.config.enable_rag:
            self._init_rag()

    def _init_rag(self) -> None:
        """初始化 RAG 系統"""
        try:
            import chromadb
            from chromadb.config import Settings
            from sentence_transformers import SentenceTransformer

            self._rag_client = chromadb.PersistentClient(
                path=str(RAG_DB_PATH), settings=Settings(anonymized_telemetry=False)
            )

            try:
                self._rag_collection = self._rag_client.get_collection("case_templates")
                logger.info(f"RAG 系統已初始化，病例範本數量: {self._rag_collection.count()}")
            except Exception:
                logger.warning("RAG 集合不存在，跳過病例範本檢索")
                self._rag_client = None
                return

            self._embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        except Exception as e:
            logger.warning(f"RAG 初始化失敗: {e}")
            self._rag_client = None

    def initialize(self, engine: Optional[Engine] = None) -> None:
        """初始化 LLM 引擎"""
        if engine:
            self._engine = engine
            return

        if USE_LLAMA_CPP:
            # 預設使用 Qwen-7B GGUF，優先使用環境變數
            env_path = os.getenv("LLAMA_MODEL_PATH")
            if env_path:
                model_path = env_path
            else:
                model_path = str(get_resource_path("models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"))
            model_config = EngineConfig(
                model_path=model_path,
                n_ctx=self.config.num_ctx,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                n_gpu_layers=0,
                n_threads=int(os.getenv("LLAMA_THREADS", "8")),
                n_batch=512,
                flash_attn=True
            )
        else:
            model_config = EngineConfig(
                model_id=self.config.model_id,
                api_base=self.config.api_base,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                num_ctx=self.config.num_ctx,
            )
        self._engine = initialize_engine(model_config)
        logger.info("SOAPGenerator initialized")

    def _load_system_prompt(self) -> str:
        """從 prompt.md 載入系統提示詞"""
        prompt_path = get_resource_path("prompt.md")
        if prompt_path.exists():
            try:
                content = prompt_path.read_text(encoding="utf-8")
                # 尋找指令開始的部分
                match = re.search(r"(You are a highly skilled Medical Scribe.*)", content, re.DOTALL)
                if match:
                    return match.group(1).strip()
            except Exception as e:
                logger.warning(f"無法讀取 prompt.md: {e}")
        
        # 預設提示詞 (Fallback)
        return "You are a professional medical scribe. Convert the transcript into a concise English SOAP note."

    def _build_prompt(
        self,
        transcript: str,
        patient_context: Optional[Dict[str, Any]] = None,
        normalized_text: str = "",
        term_mappings: Optional[List[TermMapping]] = None,
        icd10_candidates: Optional[List[str]] = None,
        case_templates: Optional[List[Dict[str, Any]]] = None,
        medical_orders: Optional[List[str]] = None,
        drug_recommendations: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """建立 SOAP 生成提示詞 (整合 prompt.md 指令與動態數據)"""

        # 準備上下文
        term_list = (
            "\n".join([f"  - {m.original} -> {m.standard}" for m in term_mappings])
            if term_mappings
            else "無"
        )
        icd_str = ", ".join(list(set(icd10_candidates))) if icd10_candidates else "無"
        orders_str = ", ".join(medical_orders) if medical_orders else "無"
        drugs_str = (
            ", ".join([f"{d['name']} ({d['dosage']})" for d in drug_recommendations])
            if drug_recommendations
            else "無"
        )

        # 準備病例範本 (RAG)
        case_templates_str = "無"
        if case_templates and len(case_templates) > 0:
            case_templates_str = ""
            for i, template in enumerate(case_templates[:3]):
                case_templates_str += f"\n【參考病例 {i + 1}】\n{template.get('content', '')[:500]}"

        # 載入指令
        system_instruction = self._load_system_prompt()

        # 組合最終 Prompt
        prompt = f"""{system_instruction}

醫療對話：
{normalized_text if normalized_text else transcript}

術語標準化參考：
{term_list}

預期診斷代碼 (ICD-10)：
{icd_str}

醫囑/處置建議：
{orders_str}

藥物建議：
{drugs_str}

參考病例範本：
{case_templates_str}

請嚴格遵循上述格式規範進行輸出。
"""
        return prompt

    def generate(
        self,
        transcript: str,
        patient_context: Optional[Dict[str, Any]] = None,
        medical_orders: Optional[List[str]] = None,
        drug_recommendations: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """生成 SOAP 病歷"""
        if not self._engine:
            self.initialize()

        # 術語標準化
        normalized_text = ""
        term_mappings: List[TermMapping] = []
        icd10_candidates: List[str] = []
        try:
            normalized_text, term_mappings = self._mapper.map_text(transcript)
            icd10_candidates = [
                code for m in term_mappings if m.icd10_candidates for code in m.icd10_candidates
            ]
        except Exception as norm_err:
            logger.warning("術語標準化失敗: %s", norm_err)

        # RAG 檢索
        case_templates = []
        if self.config.enable_rag and self._rag_client:
            try:
                case_templates = self._search_case_templates(transcript)
            except Exception as rag_err:
                logger.warning(f"RAG 檢索失敗: {rag_err}")

        prompt = self._build_prompt(
            transcript,
            patient_context,
            normalized_text=normalized_text,
            term_mappings=term_mappings,
            icd10_candidates=icd10_candidates,
            case_templates=case_templates,
            medical_orders=medical_orders,
            drug_recommendations=drug_recommendations,
        )

        try:
            logger.info(f"Generating SOAP with prompt length: {len(prompt)}")
            response = self._engine.generate(
                prompt=prompt,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
            logger.info(f"LLM Response received, length: {len(response)}")
            
            result = self._parse_response(response, transcript)
            result["normalized_terms"] = [
                {
                    "original": m.original,
                    "standard": m.standard,
                    "icd10_candidates": m.icd10_candidates,
                }
                for m in term_mappings
            ]
            result["case_templates"] = case_templates
            
            # 臨床合規性查核
            try:
                result["compliance_warnings"] = self._compliance_guard.check_compliance(result)
            except Exception as guard_err:
                logger.warning(f"臨床合規性查核失敗: {guard_err}")
                result["compliance_warnings"] = []
                
            return result
        except Exception as e:
            logger.error(f"SOAP generation error: {e}")
            raise

    def _parse_response(self, response: str, transcript: str) -> Dict[str, Any]:
        """解析 LLM 回應成結構化 SOAP"""
        logger.debug(f"Raw LLM Response: {response}")
        
        soap: Dict[str, Any] = {
            "subjective": "",
            "objective": "",
            "assessment": "",
            "plan": "",
            "conversation_summary": "",
            "raw_response": response,
        }

        # 段落樣式定義 - 針對 English 提示詞優化，並保留中文作為相容性
        patterns = {
            "subjective": r"(?:\*\*?)?(?:S:|S\s*\(Subjective\):|Subjective:|\[Subjective\]|\[病人主訴\]|\[主觀敘述\])(?:\*\*?)?\s*",
            "objective": r"(?:\*\*?)?(?:O:|O\s*\(Objective\):|Objective:|\[Objective\]|\[客觀發現\]|\[理學檢查\])(?:\*\*?)?\s*",
            "assessment": r"(?:\*\*?)?(?:A:|A\s*\(Assessment\):|Assessment:|\[Assessment\]|\[診斷評估\]|\[臨床診斷\])(?:\*\*?)?\s*",
            "plan": r"(?:\*\*?)?(?:P:|P\s*\(Plan\):|Plan:|\[Plan\]|\[治療計畫\]|\[處置建議\])(?:\*\*?)?\s*",
            "conversation_summary": r"(?:\*\*?)?(?:CONVERSATION_SUMMARY:|Summary:|對話摘要:|摘要:)(?:\*\*?)?\s*",
        }
        
        lines = response.strip().split("\n")
        current_section = None
        
        for line in lines:
            line_s = line.strip()
            if not line_s:
                continue

            matched = False
            for section, pattern in patterns.items():
                if re.search(pattern, line_s, re.I):
                    current_section = section
                    content = re.sub(pattern, "", line_s, flags=re.I).strip()
                    if content:
                        soap[current_section] += content + "\n"
                    matched = True
                    break

            if not matched and current_section:
                if any(x in line_s for x in ["字元控制", "英文專業醫師", "在此填入", "在此描述"]):
                    continue
                soap[current_section] += line_s + "\n"

        for key in ["subjective", "objective", "assessment", "plan", "conversation_summary"]:
            soap[key] = soap[key].strip()

        # Fallback: 如果四大區塊全部落空，可能是模型格式完全不對，將全文放入 Subjective
        if not any([soap["subjective"], soap["objective"], soap["assessment"], soap["plan"]]):
            logger.warning("SOAP 解析完全失敗，採用 Fallback 模式")
            soap["subjective"] = response.strip()

        return soap

    def _search_case_templates(self, query: str) -> List[Dict[str, Any]]:
        """搜尋相關病例範本 (同前)"""
        if not self._rag_client or not self._embedding_model or not self._rag_collection:
            return []
        try:
            query_embedding = self._embedding_model.encode(query)
            results = self._rag_collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=self.config.rag_top_k,
            )
            case_templates = []
            if results["documents"]:
                for i in range(len(results["documents"][0])):
                    # 取更多內容 (前 800 字元)
                    content = (
                        results["documents"][0][i][:800]
                        if len(results["documents"][0][i]) > 800
                        else results["documents"][0][i]
                    )
                    similarity = (
                        1.0 - (results["distances"][0][i] / 2) if results["distances"] else 0.5
                    )
                    case_templates.append(
                        {
                            "content": content,
                            "similarity": similarity,
                        }
                    )
            return case_templates
        except Exception as e:
            logger.warning(f"RAG 搜尋失敗: {e}")
            return []


_generator: Optional[SOAPGenerator] = None


def get_generator(config: Optional[SOAPConfig] = None) -> SOAPGenerator:
    global _generator
    if _generator is None:
        _generator = SOAPGenerator(config)
    return _generator


def initialize_generator(config: Optional[SOAPConfig] = None) -> SOAPGenerator:
    gen = get_generator(config)
    if not gen._engine:
        gen.initialize()
    return gen
