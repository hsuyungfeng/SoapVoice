#!/usr/bin/env python3
"""
SoapVoice Typer CLI 介面

提供現代化命令列介面，使用 Typer 框架
支援文字輸入、音訊處理、多種 LLM 後端
"""

import sys
import os
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# 添加專案根目錄到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.soap.soap_generator import SOAPGenerator, SOAPConfig, initialize_generator
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
        self.asr_model: Optional[WhisperModel] = None

    def initialize(self, skip_llm: bool = False) -> None:
        """初始化 ASR 與 LLM 引擎"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            if not skip_llm:
                task_llm = progress.add_task("初始化 LLM 引擎...", total=None)
                
                # 建立統一配置
                if self.backend == "llama.cpp":
                    if not self.model_path:
                        self.model_path = "models/gemma-4-E4B-it-Q4_K_M.gguf"
                    
                    # 設定環境變數讓 SOAPGenerator 使用 llama.cpp
                    os.environ["USE_LLAMA_CPP"] = "true"
                    os.environ["LLAMA_MODEL_PATH"] = self.model_path
                    
                    self.generator = initialize_generator()
                else:
                    os.environ["USE_LLAMA_CPP"] = "false"
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
        if not self.generator:
            self.initialize()
            
        # 使用統一的 SOAPGenerator，它內部會處理術語標準化、ICD-10 與資料庫查詢
        result = self.generator.generate(
            transcript=text,
            patient_context=None
        )
        
        return result

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


@app.command()
def process(
    text: Optional[str] = typer.Option(None, "--text", "-t", help="直接輸入醫療對話文字"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="從檔案讀取醫療對話"),
    audio: Optional[Path] = typer.Option(None, "--audio", "-a", help="音訊檔案路徑"),
    model: str = typer.Option("gemma-4-e4b", "--model", "-m", help="模型名稱"),
    backend: str = typer.Option("llama.cpp", "--backend", "-b", help="LLM 後端 (ollama/llama.cpp)"),
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
        console.print_json(data=result)
    else:
        console.print(f"\n[bold blue]轉錄文字:[/bold blue]\n{transcript}")
        cli.display_result(result)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8010, reload: bool = False):
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
    table.add_row("gemma-4-E4B-it-Q4_K_M.gguf", "llama.cpp")
    console.print(table)


if __name__ == "__main__":
    app()
