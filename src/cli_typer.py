#!/usr/bin/env python3
"""
SoapVoice Typer CLI 介面

提供現代化命令列介面，使用 Typer 框架
支援文字輸入、音訊處理、多種 LLM 後端
"""

import sys
from pathlib import Path
from typing import Optional, List
import logging

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# 添加專案根目錄到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.soap.soap_generator import SOAPGenerator, SOAPConfig, initialize_generator
from src.nlp.terminology_mapper import MedicalTerminologyMapper
from src.llm import LlamaEngine, LlamaConfig

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
        model: str = "qwen2.5:7b",
        backend: str = "ollama",
        model_path: Optional[str] = None,
    ):
        """初始化 CLI

        Args:
            model: Ollama 模型名稱
            backend: LLM 後端 (ollama/llama.cpp)
            model_path: llama.cpp 模型路徑
        """
        self.model = model
        self.backend = backend
        self.model_path = model_path
        self.generator: Optional[SOAPGenerator] = None
        self.llama_engine: Optional[LlamaEngine] = None
        self.terminology_mapper = MedicalTerminologyMapper()

    def initialize(self) -> None:
        """初始化 LLM 引擎"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("初始化 LLM 引擎...", total=None)

            if self.backend == "llama.cpp":
                if not self.model_path:
                    self.model_path = "models/qwen2.5-7b-instruct-q4_k_m.gguf"

                config = LlamaConfig(
                    model_path=self.model_path,
                    n_gpu_layers=0,  # CPU 模式
                    n_threads=8,
                    max_tokens=2048,
                    temperature=0.3,
                )
                self.llama_engine = LlamaEngine(config)
                self.llama_engine.initialize()
                console.print(f"[green]✓[/green] llama.cpp 引擎初始化完成")
                console.print(f"  模型: {self.model_path}")

            else:
                config = SOAPConfig(model_id=self.model)
                self.generator = initialize_generator(config)
                console.print(f"[green]✓[/green] Ollama 引擎初始化完成")
                console.print(f"  模型: {self.model}")

    def process_text(self, text: str) -> dict:
        """處理文字輸入

        Args:
            text: 醫療對話文字

        Returns:
            SOAP 結果字典
        """
        # 術語標準化
        normalized_text, term_mappings = self.terminology_mapper.map_text(text)

        # 生成 SOAP
        if self.backend == "llama.cpp" and self.llama_engine:
            return self._process_with_llama(text, term_mappings)
        else:
            result = self.generator.generate(text, None)
            result["normalized_terms"] = [
                {
                    "original": m.original,
                    "standard": m.standard,
                    "icd10_candidates": m.icd10_candidates,
                }
                for m in term_mappings
            ]
            return result

    def _process_with_llama(self, text: str, term_mappings) -> dict:
        """使用 llama.cpp 生成 SOAP

        Args:
            text: 醫療對話
            term_mappings: 術語映射

        Returns:
            SOAP 結果
        """
        if not self.llama_engine:
            raise RuntimeError("llama.cpp 引擎未初始化")

        # 建構 prompt
        term_list = "\n".join([f"- {m.original} → {m.standard}" for m in term_mappings])
        prompt = f"""請將以下醫療對話轉換為 SOAP 病歷格式（英文）。

醫療對話：
{text}

術語標準化：
{term_list}

請按照以下格式輸出：
S - Subjective (主觀陳述):
O - Objective (客觀發現):
A - Assessment (評估):
P - Plan (計畫):
"""

        result_text = self.llama_engine.generate(prompt)

        # 解析 SOAP
        return {
            "subjective": self._extract_section(result_text, "S"),
            "objective": self._extract_section(result_text, "O"),
            "assessment": self._extract_section(result_text, "A"),
            "plan": self._extract_section(result_text, "P"),
            "normalized_terms": [
                {
                    "original": m.original,
                    "standard": m.standard,
                    "icd10_candidates": m.icd10_candidates,
                }
                for m in term_mappings
            ],
            "raw_output": result_text,
        }

    def _extract_section(self, text: str, section: str) -> str:
        """從文字中提取 SOAP 段落

        Args:
            text: 完整文字
            section: 段落標題 (S/O/A/P)

        Returns:
            段落內容
        """
        import re

        pattern = rf"{section}\s*[-:]\s*(.+?)(?=\n[A-Z]\s*[-:]|$)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    def display_result(self, result: dict) -> None:
        """顯示結果

        Args:
            result: SOAP 結果
        """
        # 建立表格
        table = Table(title="SOAP 病歷結果", show_header=True, header_style="bold magenta")
        table.add_column("項目", style="cyan", width=12)
        table.add_column("內容", style="white")

        if result.get("subjective"):
            table.add_row(
                "S (主觀)",
                result["subjective"][:200] + "..."
                if len(result["subjective"]) > 200
                else result["subjective"],
            )

        if result.get("objective"):
            table.add_row(
                "O (客觀)",
                result["objective"][:200] + "..."
                if len(result["objective"]) > 200
                else result["objective"],
            )

        if result.get("assessment"):
            table.add_row(
                "A (評估)",
                result["assessment"][:200] + "..."
                if len(result["assessment"]) > 200
                else result["assessment"],
            )

        if result.get("plan"):
            table.add_row(
                "P (計畫)",
                result["plan"][:200] + "..." if len(result["plan"]) > 200 else result["plan"],
            )

        console.print(table)

        # 術語標準化
        if result.get("normalized_terms"):
            console.print("\n[bold]術語標準化:[/bold]")
            for term in result["normalized_terms"]:
                icd10 = (
                    f" ({', '.join(term['icd10_candidates'])})"
                    if term.get("icd10_candidates")
                    else ""
                )
                console.print(f"  • {term['original']} → {term['standard']}{icd10}")


@app.command()
def main(
    text: Optional[str] = typer.Option(None, "--text", "-t", help="直接輸入醫療對話文字"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="從檔案讀取醫療對話"),
    audio: Optional[Path] = typer.Option(None, "--audio", "-a", help="音訊檔案路徑"),
    model: str = typer.Option("qwen2.5:7b", "--model", "-m", help="Ollama 模型名稱"),
    backend: str = typer.Option("ollama", "--backend", "-b", help="LLM 後端 (ollama/llama.cpp)"),
    model_path: Optional[str] = typer.Option(None, "--model-path", help="llama.cpp 模型路徑"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="顯示詳細日誌"),
):
    """SoapVoice CLI 主命令"""

    # 設置日誌
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)s: %(message)s",
    )

    # 驗證輸入
    if not text and not file and not audio:
        console.print("[red]錯誤:[/red] 請提供 --text、--file 或 --audio 參數")
        console.print("使用 --help 查看更多資訊")
        raise typer.Exit(code=1)

    # 讀取檔案
    transcript = ""
    if file:
        try:
            transcript = file.read_text(encoding="utf-8").strip()
        except Exception as e:
            console.print(f"[red]錯誤:[/red] 讀取檔案失敗: {e}")
            raise typer.Exit(code=1)

    # 讀取文字
    if text:
        transcript = text

    # 音訊處理（TODO: 未來擴展）
    if audio:
        console.print("[yellow]注意:[/yellow] 音訊處理功能尚未完成，請使用文字輸入")
        raise typer.Exit(code=1)

    if not transcript:
        console.print("[red]錯誤:[/red] 未找到有效輸入")
        raise typer.Exit(code=1)

    # 初始化 CLI
    cli = SoapVoiceTyperCLI(model=model, backend=backend, model_path=model_path)

    try:
        cli.initialize()
    except Exception as e:
        console.print(f"[red]錯誤:[/red] 初始化失敗: {e}")
        raise typer.Exit(code=1)

    # 處理輸入
    with Progress(console=console) as progress:
        task = progress.add_task("生成 SOAP 病歷...", total=None)
        try:
            result = cli.process_text(transcript)
            progress.update(task, completed=True)
        except Exception as e:
            console.print(f"[red]錯誤:[/red] 生成失敗: {e}")
            raise typer.Exit(code=1)

    # 顯示結果
    cli.display_result(result)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="伺服器位址"),
    port: int = typer.Option(8000, "--port", help="伺服器連接埠"),
    reload: bool = typer.Option(False, "--reload", help="開發模式自動重載"),
):
    """啟動 SoapVoice API 伺服器"""
    import uvicorn

    console.print(f"[green]啟動伺服器:[/green] http://{host}:{port}")

    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def models():
    """列出可用的 LLM 模型"""
    table = Table(title="LLM 模型", show_header=True)
    table.add_column("名稱", style="cyan")
    table.add_column("後端", style="green")
    table.add_column("說明", style="white")

    # Ollama 模型
    table.add_row("qwen2.5:14b", "Ollama", "大型模型，準確度高")
    table.add_row("qwen2.5:7b", "Ollama", "平衡模型，推薦使用")
    table.add_row("qwen2.5:3b", "Ollama", "快速模型，資源需求低")

    # llama.cpp
    table.add_row("qwen2.5-7b-q4_k_m", "llama.cpp", "CPU 模式，約 4.5GB")

    console.print(table)


if __name__ == "__main__":
    app()
