#!/usr/bin/env python3
"""
SoapVoice Typer CLI 介面

提供現代化命令列介面，使用 Typer 框架
支援文字輸入、音訊處理、多種 LLM 後端
"""

import sys
import re
import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# 添加專案根目錄到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.soap.soap_generator import SOAPGenerator, SOAPConfig, initialize_generator
from src.nlp.terminology_mapper import MedicalTerminologyMapper
from src.nlp.icd10_classifier import ICD10Classifier
from src.db.clinical_db import ClinicalDatabase
from src.llm import LlamaEngine, LlamaConfig
from src.asr.whisper_model import WhisperModel

app = typer.Typer(
    name="soapvoice",
    help="SoapVoice - 醫療語音轉 SOAP 病歷系統",
    add_completion=False,
)

console = Console()
logger = logging.getLogger(__name__)


class SoapVoiceTyperCLI:
    """SoapVoice Typer CLI 核心類別"""

    def __init__(
        self,
        model: str = "gemma-4-e4b",
        backend: str = "llama.cpp",
        model_path: Optional[str] = None,
        whisper_model_id: str = "medium",
        whisper_device: str = "cpu",
    ):
        """初始化 CLI"""
        self.model = model
        self.backend = backend
        self.model_path = model_path
        self.whisper_model_id = whisper_model_id
        self.whisper_device = whisper_device
        
        self.generator: Optional[SOAPGenerator] = None
        self.llama_engine: Optional[LlamaEngine] = None
        self.asr_model: Optional[WhisperModel] = None
        
        self.terminology_mapper = MedicalTerminologyMapper()
        self.icd10_classifier = ICD10Classifier()
        self.clinical_db = ClinicalDatabase()

    def initialize(self, skip_llm: bool = False) -> None:
        """初始化 ASR 與 LLM 引擎"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            if not skip_llm:
                task_llm = progress.add_task("初始化 LLM 引擎...", total=None)
                if self.backend == "llama.cpp":
                    if not self.model_path:
                        self.model_path = "models/gemma-4-E4B-it-Q4_K_M.gguf"
                    config = LlamaConfig(
                        model_path=self.model_path,
                        n_gpu_layers=0,
                        n_threads=8,
                        max_tokens=2048,
                        temperature=0.3,
                    )
                    self.llama_engine = LlamaEngine(config)
                    self.llama_engine.initialize()
                else:
                    config = SOAPConfig(model_id=self.model)
                    self.generator = initialize_generator(config)
                progress.update(task_llm, completed=True)

    def initialize_asr(self) -> None:
        """初始化 ASR 引擎"""
        if not self.asr_model:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task_asr = progress.add_task(f"載入 Whisper {self.whisper_model_id} 模型 ({self.whisper_device})...", total=None)
                compute_type = "int8" if self.whisper_device == "cpu" else "float16"
                self.asr_model = WhisperModel(
                    model_id=self.whisper_model_id,
                    device=self.whisper_device,
                    compute_type=compute_type
                )
                progress.update(task_asr, completed=True)

    def transcribe(self, audio_path: Path) -> str:
        """語音轉文字"""
        self.initialize_asr()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"正在轉錄 {audio_path.name}...", total=None)
            result = self.asr_model.transcribe(str(audio_path))
            progress.update(task, completed=True)
            return result["text"]

    def process_text(self, text: str) -> dict:
        """處理文字輸入並生成 SOAP"""
        # 術語標準化
        _, term_mappings = self.terminology_mapper.map_text(text)
        symptoms = [m.standard for m in term_mappings]

        # 進行 ICD-10 分類
        icd10_matches = self.icd10_classifier.classify(text)
        icd10_codes = [m.code for m in icd10_matches]

        # 查詢醫囑與藥物
        medical_orders = self.clinical_db.get_medical_orders(symptoms, icd10_codes)
        drug_recommendations = self.clinical_db.get_drug_recommendations(symptoms, icd10_codes)

        # 生成 SOAP
        if self.backend == "llama.cpp" and self.llama_engine:
            return self._process_with_llama(
                text, term_mappings, medical_orders, drug_recommendations
            )
        else:
            if not self.generator:
                self.initialize()
            result = self.generator.generate(
                transcript=text,
                patient_context=None,
                medical_orders=medical_orders,
                drug_recommendations=drug_recommendations,
            )
            result["normalized_terms"] = [
                {"original": m.original, "standard": m.standard, "icd10_candidates": m.icd10_candidates}
                for m in term_mappings
            ]
            result["medical_orders"] = medical_orders
            result["drug_recommendations"] = drug_recommendations
            return result

    def _process_with_llama(
        self, text: str, term_mappings, medical_orders: List[str], drug_recommendations: List[dict]
    ) -> dict:
        """使用 llama.cpp 生成 SOAP (同步自 prompt.md)"""
        term_list = "\n".join([f"  - {m.original} -> {m.standard}" for m in term_mappings])
        orders_str = ", ".join(medical_orders) if medical_orders else "無"
        drugs_str = ", ".join([f"{d['name']} ({d['dosage']})" for d in drug_recommendations]) if drug_recommendations else "無"

        prompt = f"""你是專業的醫療記錄助理。請將醫師與病患的語音記錄轉換成標準詳細的 SOAP 格式病歷，並整理聊天摘要。

醫療對話：
{text}

術語標準化參考：
{term_list}

預期診斷代碼 (ICD-10)：
無

醫囑/處置建議：
{orders_str}

藥物建議：
{drugs_str}

請按照以下格式輸出：

1. SOAP 格式病歷 (使用英文專業醫師用語):

S (Subjective - 主訴):
[內容]

O (Objective - 客觀發現):
[內容]

A (Assessment - 評估診斷):
[內容]

P (Plan):
[內容]

2. 對話摘要 (使用繁體中文，在最後加上):

CONVERSATION_SUMMARY:
[繁體中文總結]
"""
        result_text = self.llama_engine.generate(prompt)
        
        # 清理幻覺內容 (模型可能會在總結後繼續生成內容)
        result_text = self._clean_hallucinated_output(result_text)

        return {
            "subjective": self._extract_section(result_text, "S"),
            "objective": self._extract_section(result_text, "O"),
            "assessment": self._extract_section(result_text, "A"),
            "plan": self._extract_section(result_text, "P"),
            "conversation_summary": self._extract_section(result_text, "CONVERSATION_SUMMARY"),
            "normalized_terms": [
                {"original": m.original, "standard": m.standard, "icd10_candidates": m.icd10_candidates}
                for m in term_mappings
            ],
            "raw_output": result_text,
            "medical_orders": medical_orders,
            "drug_recommendations": drug_recommendations,
        }

    def _extract_section(self, text: str, section: str) -> str:
        """從文字中提取指定段落"""
        if section == "CONVERSATION_SUMMARY":
            pattern = r"CONVERSATION_SUMMARY\s*[:：]\s*(.*)"
        else:
            pattern = rf"{section}\s*\(.*?\)\s*[:：]\s*(.*?)(?=\n[A-P]\s*\(|\nCONVERSATION_SUMMARY|$)"
            if not re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                pattern = rf"{section}\s*[:：]\s*(.*?)(?=\n[OAP]|[\n]CONVERSATION_SUMMARY|$)"
        match = re.search(pattern, text, re.I | re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def display_result(self, result: dict) -> None:
        """顯示結果"""
        table = Table(title="SOAP 病歷結果", show_header=True, header_style="bold magenta")
        table.add_column("項目", style="cyan", width=15)
        table.add_column("內容", style="white")

        for key, name in [("subjective", "S (主觀)"), ("objective", "O (客觀)"), ("assessment", "A (評估)"), ("plan", "P (計畫)"), ("conversation_summary", "對話摘要 (中)")]:
            if result.get(key):
                table.add_row(name, result[key])

        console.print(table)

        if result.get("normalized_terms"):
            console.print("\n[bold]術語與診斷建議:[/bold]")
            for term in result["normalized_terms"]:
                icd10 = f" ({', '.join(term['icd10_candidates'])})" if term.get("icd10_candidates") else ""
                console.print(f"  - {term['original']} -> [green]{term['standard']}[/green]{icd10}")

    def _clean_hallucinated_output(self, text: str) -> str:
        """清理模型幻覺生成的後續對話或標籤"""
        # 如果發現 CONVERSATION_SUMMARY 後面還有對話標籤，則切掉
        patterns = [
            r"\n\n\s*Assistant\s*:",
            r"\n\n\s*User\s*:",
            r"\n\n\s*醫師\s*[:：]",
            r"\n\n\s*病患\s*[:：]",
            r"\n\n\s*醫生\s*[:：]",
            r"\n\n\s*Note\s*[:：]",
            r"\n\n\s*病例總結\s*[:：]",
        ]
        
        # 尋找 CONVERSATION_SUMMARY 的位置
        summary_idx = text.find("CONVERSATION_SUMMARY")
        if summary_idx != -1:
            # 只在摘要之後進行切除
            after_summary = text[summary_idx:]
            for p in patterns:
                m = re.search(p, after_summary, re.I)
                if m:
                    # 切掉匹配點之後的所有內容
                    text = text[:summary_idx + m.start()]
                    break
                    
        return text.strip()


@app.command()
def process(
    text: Optional[str] = typer.Option(None, "--text", "-t", help="直接輸入醫療對話文字"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="從檔案讀取醫療對話"),
    audio: Optional[Path] = typer.Option(None, "--audio", "-a", help="音訊檔案路徑"),
    model: str = typer.Option("qwen2.5:7b", "--model", "-m", help="Ollama 模型名稱"),
    backend: str = typer.Option("ollama", "--backend", "-b", help="LLM 後端 (ollama/llama.cpp)"),
    model_path: Optional[str] = typer.Option(None, "--model-path", help="llama.cpp 模型路徑"),
    whisper_model: str = typer.Option("medium", "--whisper-model", help="Whisper 模型 (tiny/base/small/medium/large)"),
    whisper_device: str = typer.Option("cpu", "--whisper-device", help="Whisper 執行設備 (cpu/cuda)"),
    json_output: bool = typer.Option(False, "--json", help="以 JSON 格式輸出結果"),
):
    """處理音訊或文字並生成 SOAP"""
    cli = SoapVoiceTyperCLI(
        model=model, 
        backend=backend, 
        model_path=model_path,
        whisper_model_id=whisper_model,
        whisper_device=whisper_device
    )
    
    transcript = ""
    if audio:
        transcript = cli.transcribe(audio)
    elif file:
        transcript = file.read_text(encoding="utf-8").strip()
    elif text:
        transcript = text
        
    if not transcript:
        console.print("[red]錯誤:[/red] 未找到有效輸入或轉錄失敗")
        raise typer.Exit(code=1)

    cli.initialize()
    result = cli.process_text(transcript)
    result["transcript"] = transcript

    if json_output:
        import json
        console.print_json(data=result)
    else:
        console.print(f"\n[bold blue]轉錄文字:[/bold blue]\n{transcript}")
        cli.display_result(result)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """啟動 API 伺服器"""
    import uvicorn
    console.print(f"[green]啟動伺服器:[/green] http://{host}:{port}")
    uvicorn.run("src.main:app", host=host, port=port, reload=reload)


@app.command()
def models():
    """列出可用模型"""
    table = Table(title="LLM 模型")
    table.add_column("名稱", style="cyan")
    table.add_column("後端", style="green")
    table.add_row("qwen2.5:7b", "Ollama")
    table.add_row("Qwen2.5-7B-Instruct-GGUF", "llama.cpp")
    console.print(table)


if __name__ == "__main__":
    app()
