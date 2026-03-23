"""
NotebookLM 適配器

提供與 NotebookLM MCP CLI 的整合，用於增強醫療資料庫搜尋功能
"""

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import os
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class NotebookLMQuery:
    """NotebookLM 查詢參數"""
    query: str
    context: Optional[str] = None
    sources: Optional[List[str]] = None
    max_results: int = 10
    include_citations: bool = True
    language: str = "zh-tw"


@dataclass
class MedicalSearchResult:
    """醫療搜尋結果"""
    query: str
    diagnosis_suggestions: List[Dict[str, Any]]
    treatment_protocols: List[Dict[str, Any]]
    drug_recommendations: List[Dict[str, Any]]
    evidence_summary: str
    confidence_scores: Dict[str, float]
    sources: List[Dict[str, Any]]


class NotebookLMAdapter:
    """NotebookLM MCP CLI 適配器
    
    整合 NotebookLM 的深度搜尋功能，增強醫療資料庫查詢
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 NotebookLM 適配器"""
        self.config = config or {}
        self.notebooklm_cli_path = self.config.get("notebooklm_cli_path", "notebooklm-mcp-cli")
        self.default_sources = self.config.get("default_sources", [])
        self.cache_enabled = self.config.get("cache_enabled", True)
        self.cache_dir = Path(os.path.expanduser(self.config.get("cache_dir", "~/.cache/clivoice/notebooklm")))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._medical_databases = {}
        logger.info(f"NotebookLM 適配器初始化完成，快取目錄: {self.cache_dir}")
    
    def _execute_notebooklm_command(self, command: str, args: List[str]) -> Dict[str, Any]:
        """執行 NotebookLM CLI 命令"""
        try:
            cmd = [self.notebooklm_cli_path, command] + args
            logger.debug(f"執行 NotebookLM 命令: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.error(f"NotebookLM 命令失敗: {result.stderr}")
                raise RuntimeError(f"NotebookLM 命令失敗: {result.stderr}")
            
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"output": result.stdout.strip()}
                
        except subprocess.TimeoutExpired:
            logger.error("NotebookLM 命令執行超時")
            raise RuntimeError("NotebookLM 命令執行超時")
        except FileNotFoundError:
            logger.error(f"找不到 NotebookLM CLI: {self.notebooklm_cli_path}")
            raise RuntimeError(f"找不到 NotebookLM CLI: {self.notebooklm_cli_path}")
    
    def _get_cache_key(self, query: str, context: Optional[str] = None) -> str:
        """產生快取鍵值"""
        content = f"{query}:{context or ''}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _load_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """從快取載入資料"""
        if not self.cache_enabled:
            return None
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"載入快取失敗: {e}")
                return None
        return None
    
    def _save_to_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """儲存資料到快取"""
        if not self.cache_enabled:
            return
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.warning(f"儲存快取失敗: {e}")
    
    def search_medical_database(self, query: NotebookLMQuery) -> MedicalSearchResult:
        """搜尋醫療資料庫"""
        cache_key = self._get_cache_key(query.query, query.context)
        cached_result = self._load_from_cache(cache_key)
        
        if cached_result:
            logger.info(f"從快取載入醫療搜尋結果: {query.query}")
            return MedicalSearchResult(**cached_result)
        
        logger.info(f"執行醫療資料庫搜尋: {query.query}")
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                query_data = {
                    "query": query.query,
                    "context": query.context,
                    "sources": query.sources or self.default_sources,
                    "max_results": query.max_results,
                    "include_citations": query.include_citations,
                    "language": query.language
                }
                json.dump(query_data, f, ensure_ascii=False)
                query_file = f.name
            
            result = self._execute_notebooklm_command("search", [
                "--query-file", query_file,
                "--format", "json",
                "--max-results", str(query.max_results)
            ])
            
            os.unlink(query_file)
            medical_result = self._parse_medical_search_result(result, query)
            self._save_to_cache(cache_key, asdict(medical_result))
            
            return medical_result
            
        except Exception as e:
            logger.error(f"醫療資料庫搜尋失敗: {e}")
            return MedicalSearchResult(
                query=query.query,
                diagnosis_suggestions=[],
                treatment_protocols=[],
                drug_recommendations=[],
                evidence_summary="搜尋失敗，請檢查 NotebookLM 設定",
                confidence_scores={},
                sources=[]
            )
    
    def _parse_medical_search_result(self, notebooklm_result: Dict[str, Any], 
                                   query: NotebookLMQuery) -> MedicalSearchResult:
        """解析 NotebookLM 搜尋結果"""
        diagnosis_suggestions = []
        treatment_protocols = []
        drug_recommendations = []
        sources = []
        
        if "results" in notebooklm_result:
            for result_item in notebooklm_result["results"]:
                content = result_item.get("content", "")
                metadata = result_item.get("metadata", {})
                source_type = metadata.get("source_type", "unknown")
                
                if self._is_diagnosis_content(content):
                    diagnosis_suggestions.append({
                        "content": content,
                        "source": source_type,
                        "confidence": result_item.get("confidence", 0.5),
                        "metadata": metadata
                    })
                elif self._is_treatment_content(content):
                    treatment_protocols.append({
                        "content": content,
                        "source": source_type,
                        "confidence": result_item.get("confidence", 0.5),
                        "metadata": metadata
                    })
                elif self._is_drug_content(content):
                    drug_recommendations.append({
                        "content": content,
                        "source": source_type,
                        "confidence": result_item.get("confidence", 0.5),
                        "metadata": metadata
                    })
                
                if "citations" in result_item:
                    sources.extend(result_item["citations"])
        
        evidence_summary = self._generate_evidence_summary(
            diagnosis_suggestions, treatment_protocols, drug_recommendations
        )
        
        confidence_scores = {
            "diagnosis": self._calculate_confidence(diagnosis_suggestions),
            "treatment": self._calculate_confidence(treatment_protocols),
            "drug": self._calculate_confidence(drug_recommendations),
            "overall": min(
                self._calculate_confidence(diagnosis_suggestions),
                self._calculate_confidence(treatment_protocols),
                self._calculate_confidence(drug_recommendations)
            )
        }
        
        return MedicalSearchResult(
            query=query.query,
            diagnosis_suggestions=diagnosis_suggestions,
            treatment_protocols=treatment_protocols,
            drug_recommendations=drug_recommendations,
            evidence_summary=evidence_summary,
            confidence_scores=confidence_scores,
            sources=sources
        )
    
    def _is_diagnosis_content(self, content: str) -> bool:
        """判斷內容是否為診斷相關"""
        diagnosis_keywords = ["診斷", "疾病", "症狀", "徵候", "ICD", "病名", "確診"]
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in diagnosis_keywords)
    
    def _is_treatment_content(self, content: str) -> bool:
        """判斷內容是否為治療相關"""
        treatment_keywords = ["治療", "處置", "手術", "療法", "protocol", "guideline", "指引"]
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in treatment_keywords)
    
    def _is_drug_content(self, content: str) -> bool:
        """判斷內容是否為藥物相關"""
        drug_keywords = ["藥物", "藥品", "處方", "用藥", "ATC", "劑量", "給藥"]
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in drug_keywords)
    
    def _generate_evidence_summary(self, diagnoses: List[Dict], treatments: List[Dict], drugs: List[Dict]) -> str:
        """產生證據摘要"""
        summary_parts = []
        
        if diagnoses:
            summary_parts.append(f"找到 {len(diagnoses)} 個相關診斷建議")
        if treatments:
            summary_parts.append(f"找到 {len(treatments)} 個治療方案")
        if drugs:
            summary_parts.append(f"找到 {len(drugs)} 個藥物建議")
        
        return "；".join(summary_parts) + "。" if summary_parts else "未找到相關醫療資訊"
    
    def _calculate_confidence(self, items: List[Dict]) -> float:
        """計算信心分數"""
        if not items:
            return 0.0
        confidences = [item.get("confidence", 0.0) for item in items]
        return sum(confidences) / len(confidences)
    
    def search_symptoms(self, symptoms: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """搜尋症狀相關診斷"""
        query = NotebookLMQuery(
            query=f"根據以下症狀提供可能的診斷：{symptoms}",
            context="請提供 ICD-10 診斷代碼和疾病名稱",
            max_results=max_results
        )
        result = self.search_medical_database(query)
        return result.diagnosis_suggestions
    
    def search_treatment_protocols(self, diagnosis: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """搜尋診斷相關治療方案"""
        query = NotebookLMQuery(
            query=f"針對診斷 '{diagnosis}' 的標準治療方案",
            context="請提供治療指引、手朮建議、處置流程",
            max_results=max_results
        )
        result = self.search_medical_database(query)
        return result.treatment_protocols
    
    def search_drug_recommendations(self, diagnosis: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """搜尋診斷相關藥物建議"""
        query = NotebookLMQuery(
            query=f"針對診斷 '{diagnosis}' 的藥物治療建議",
            context="請提供藥物名稱、ATC 分類、劑量、用藥指引",
            max_results=max_results
        )
        result = self.search_medical_database(query)
        return result.drug_recommendations
    
    def enhance_diagnosis(self, diagnosis_code: str, diagnosis_name: str) -> Dict[str, Any]:
        """增強診斷資訊"""
        query = NotebookLMQuery(
            query=f"診斷 {diagnosis_name} ({diagnosis_code}) 的詳細資訊",
            context="請提供流行病學、病理生理學、臨床表現、診斷標準、預後",
            max_results=5
        )
        
        result = self.search_medical_database(query)
        
        return {
            "code": diagnosis_code,
            "name": diagnosis_name,
            "enhanced_info": {
                "epidemiology": "包含流行病學資訊" if "流行" in result.evidence_summary else "流行病學資訊待補充",
                "clinical_features": "包含臨床特徵描述" if "臨床" in result.evidence_summary else "臨床特徵待補充",
                "diagnostic_criteria": "包含診斷標準" if "標準" in result.evidence_summary else "診斷標準待補充",
                "prognosis": "包含預後資訊" if "預後" in result.evidence_summary else "預後資訊待補充",
                "evidence_summary": result.evidence_summary,
                "sources": result.sources[:3]
            },
            "confidence": result.confidence_scores.get("overall", 0.0)
        }
