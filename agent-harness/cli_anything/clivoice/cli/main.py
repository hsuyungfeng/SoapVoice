"""主 CLI 模組 — 提供 Click 命令列介面"""

import json
import sys
from typing import Optional
from pathlib import Path

import click

from ..models.soap_note import SOAPNote
from ..core.diagnosis_engine import DiagnosisEngine
from ..core.integration_orchestrator import IntegrationOrchestrator


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """CliVoice — 醫療語音轉 SOAP 病歷系統的 CLI 介面

    整合三個醫療子系統：
    1. ICD10v2 — 疾病診斷代碼系統
    2. medicalordertreeview — 醫療服務支付標準系統
    3. ATCcodeTW — 台灣 ATC 藥物分類系統
    """
    pass


@cli.command()
@click.argument("soap_text", type=str)
@click.option("--output", "-o", type=click.Path(), help="輸出檔案路徑")
@click.option("--json", "json_output", is_flag=True, help="以 JSON 格式輸出")
@click.option("--verbose", "-v", is_flag=True, help="顯示詳細資訊")
def analyze(soap_text: str, output: Optional[str], json_output: bool, verbose: bool):
    """分析 SOAP 病歷並生成診斷、醫囑和藥物建議"""

    try:
        # 解析 SOAP 病歷
        soap_note = SOAPNote.from_text(soap_text)

        if verbose:
            click.echo(f"✓ 解析 SOAP 病歷完成")
            click.echo(f"  主訴: {soap_note.subjective}")
            click.echo(f"  客觀發現: {soap_note.objective}")
            click.echo(f"  評估: {soap_note.assessment}")
            click.echo(f"  計畫: {soap_note.plan}")

        # 初始化診斷引擎
        diagnosis_engine = DiagnosisEngine()

        # 提取症狀並匹配診斷
        symptoms = diagnosis_engine.extract_symptoms(soap_note)
        diagnoses = diagnosis_engine.match_diagnoses(symptoms)

        if verbose:
            click.echo(f"✓ 提取到 {len(symptoms)} 個症狀")
            click.echo(f"✓ 匹配到 {len(diagnoses.diagnoses)} 個診斷")

        # 初始化整合協調器
        orchestrator = IntegrationOrchestrator()

        # 執行完整流程
        result = orchestrator.process_soap_note(soap_note)

        # 輸出結果
        if json_output:
            output_data = result.to_dict()
            output_str = json.dumps(output_data, ensure_ascii=False, indent=2)
        else:
            output_str = str(result)

        if output:
            Path(output).write_text(output_str, encoding="utf-8")
            click.echo(f"✓ 結果已儲存至: {output}")
        else:
            click.echo(output_str)

    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="輸出檔案路徑")
@click.option("--batch", is_flag=True, help="批次處理模式")
def batch_process(input_file: str, output: Optional[str], batch: bool):
    """批次處理 SOAP 病歷檔案"""

    input_path = Path(input_file)

    if not input_path.exists():
        click.echo(f"錯誤: 輸入檔案不存在: {input_file}", err=True)
        sys.exit(1)

    try:
        # 讀取輸入檔案
        content = input_path.read_text(encoding="utf-8")

        if batch:
            # 批次處理模式 (每行一個 SOAP 病歷)
            soap_texts = [line.strip() for line in content.splitlines() if line.strip()]
            results = []

            with click.progressbar(soap_texts, label="處理中") as bar:
                for soap_text in bar:
                    try:
                        soap_note = SOAPNote.from_text(soap_text)
                        orchestrator = IntegrationOrchestrator()
                        result = orchestrator.process_soap_note(soap_note)
                        results.append(result.to_dict())
                    except Exception as e:
                        click.echo(f"\n警告: 處理失敗: {e}", err=True)
                        continue

            output_data = {"results": results, "total": len(results)}
            output_str = json.dumps(output_data, ensure_ascii=False, indent=2)

        else:
            # 單一檔案處理模式
            soap_note = SOAPNote.from_text(content)
            orchestrator = IntegrationOrchestrator()
            result = orchestrator.process_soap_note(soap_note)
            output_str = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

        # 輸出結果
        if output:
            Path(output).write_text(output_str, encoding="utf-8")
            click.echo(f"✓ 結果已儲存至: {output}")
        else:
            click.echo(output_str)

    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("symptom", type=str)
@click.option("--limit", type=int, default=5, help="顯示結果數量限制")
def diagnose(symptom: str, limit: int):
    """根據症狀查詢可能的診斷"""

    try:
        diagnosis_engine = DiagnosisEngine()
        diagnosis_result = diagnosis_engine.match_diagnoses([symptom])

        if not diagnosis_result.diagnoses:
            click.echo(f"未找到與症狀 '{symptom}' 相關的診斷")
            return

        click.echo(f"找到 {len(diagnosis_result.diagnoses)} 個可能的診斷:")
        for i, diagnosis in enumerate(diagnosis_result.diagnoses[:limit], 1):
            click.echo(f"{i}. {diagnosis.icd10_code} - {diagnosis.name}")
            click.echo(f"   英文名稱: {diagnosis.name_en or 'N/A'}")
            if diagnosis.confidence > 0.7:
                click.echo(f"   ⭐ 高信心度 ({diagnosis.confidence:.1%})")
            click.echo()

    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("diagnosis_code", type=str)
@click.option("--category", type=str, help="醫囑類別篩選")
def orders(diagnosis_code: str, category: Optional[str]):
    """根據診斷代碼查詢相關醫囑"""

    try:
        from ..adapters.medical_order_adapter import MedicalOrderAdapter

        adapter = MedicalOrderAdapter()
        orders = adapter.get_orders_by_diagnosis(diagnosis_code, category)

        if not orders:
            click.echo(f"未找到與診斷代碼 '{diagnosis_code}' 相關的醫囑")
            return

        click.echo(f"找到 {len(orders)} 個相關醫囑:")
        for i, order in enumerate(orders, 1):
            click.echo(f"{i}. {order.code} - {order.name}")
            click.echo(f"   類別: {order.category or 'N/A'}")
            click.echo(f"   類型: {order.order_type.value}")
            if order.description:
                click.echo(f"   描述: {order.description}")
            click.echo()

    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("diagnosis_code", type=str)
@click.option("--atc-class", type=str, help="ATC 分類篩選")
def drugs(diagnosis_code: str, atc_class: Optional[str]):
    """根據診斷代碼查詢建議藥物"""

    try:
        from ..adapters.atc_drug_adapter import ATCDrugAdapter

        adapter = ATCDrugAdapter()
        drugs = adapter.get_drugs_by_diagnosis(diagnosis_code, atc_class)

        if not drugs:
            click.echo(f"未找到與診斷代碼 '{diagnosis_code}' 相關的藥物")
            return

        click.echo(f"找到 {len(drugs)} 個建議藥物:")
        for i, drug in enumerate(drugs, 1):
            click.echo(f"{i}. {drug.drug.name} - {drug.drug.generic_name or 'N/A'}")
            click.echo(f"   ATC: {drug.drug.atc_code}")
            click.echo(f"   劑型: {drug.drug.form.value if drug.drug.form else 'N/A'}")
            click.echo(f"   劑量: {drug.dosage} {drug.frequency} {drug.duration}")
            click.echo()

    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        sys.exit(1)


@cli.command()
def repl():
    """進入互動式 REPL 模式"""

    click.echo("歡迎使用 CliVoice REPL 模式!")
    click.echo("輸入 'help' 查看可用命令，輸入 'exit' 離開")
    click.echo()

    while True:
        try:
            command = click.prompt("clivoice>", type=str).strip()

            if not command:
                continue

            if command.lower() in ["exit", "quit", "q"]:
                click.echo("再見!")
                break

            if command.lower() == "help":
                click.echo("可用命令:")
                click.echo("  diagnose <症狀> — 根據症狀查詢診斷")
                click.echo("  orders <診斷代碼> — 查詢相關醫囑")
                click.echo("  drugs <診斷代碼> — 查詢建議藥物")
                click.echo("  analyze <SOAP文字> — 分析 SOAP 病歷")
                click.echo("  exit — 離開 REPL")
                continue

            # 簡單的命令解析
            parts = command.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == "diagnose" and arg:
                ctx = click.Context(diagnose)
                ctx.invoke(diagnose, symptom=arg)
            elif cmd == "orders" and arg:
                ctx = click.Context(orders)
                ctx.invoke(orders, diagnosis_code=arg)
            elif cmd == "drugs" and arg:
                ctx = click.Context(drugs)
                ctx.invoke(drugs, diagnosis_code=arg)
            elif cmd == "analyze" and arg:
                ctx = click.Context(analyze)
                ctx.invoke(analyze, soap_text=arg, json_output=False)
            else:
                click.echo(f"未知命令: {command}")
                click.echo("輸入 'help' 查看可用命令")

        except KeyboardInterrupt:
            click.echo("\n再見!")
            break
        except Exception as e:
            click.echo(f"錯誤: {e}", err=True)


if __name__ == "__main__":
    cli()
