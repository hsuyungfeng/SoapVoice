#!/usr/bin/env python3
"""
SoapVoice CLI 互動介面

提供命令列介面讓使用者輸入醫療對話，並使用較小模型（qwen3.5:9b）生成 SOAP 病歷記錄。
"""

import argparse
import sys
import logging
from typing import Optional, Dict, Any
from pathlib import Path

# 添加專案根目錄到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.soap.soap_generator import SOAPGenerator, SOAPConfig, initialize_generator
from src.nlp.terminology_mapper import MedicalTerminologyMapper


logger = logging.getLogger(__name__)


class SoapVoiceCLI:
    """SoapVoice 命令列互動介面"""

    def __init__(self, config: Optional[SOAPConfig] = None):
        """初始化 CLI

        Args:
            config: SOAP 生成配置，預設使用 qwen3.5:9b 模型
        """
        self.config = config or SOAPConfig(model_id="qwen3.5:9b")
        self.generator: Optional[SOAPGenerator] = None
        self.terminology_mapper = MedicalTerminologyMapper()

    def initialize(self) -> None:
        """初始化 SOAP 生成器"""
        try:
            self.generator = initialize_generator(self.config)
            logger.info(f"SOAP 生成器初始化完成，使用模型: {self.config.model_id}")
        except Exception as e:
            logger.error(f"初始化失敗: {e}")
            print(f"❌ 初始化失敗: {e}")
            print("請確認 Ollama 服務是否運行中 (ollama serve)")
            sys.exit(1)

    def interactive_input(self) -> Dict[str, Any]:
        """互動式輸入醫療對話與病患資訊

        Returns:
            包含 transcript 和 patient_context 的字典
        """
        print("=" * 60)
        print("SoapVoice - 醫療語音轉 SOAP 病歷系統")
        print("=" * 60)
        print("\n請輸入醫療對話內容（輸入空行結束）：")

        # 收集多行輸入
        lines = []
        while True:
            try:
                line = input("> ")
                if line.strip() == "":
                    break
                lines.append(line)
            except EOFError:
                print("\n輸入結束")
                break
            except KeyboardInterrupt:
                print("\n\n操作取消")
                sys.exit(0)

        transcript = "\n".join(lines)

        if not transcript.strip():
            print("❌ 未輸入任何對話內容")
            sys.exit(1)

        # 收集病患背景資訊（可選）
        patient_context = {}
        print("\n請輸入病患背景資訊（可選，直接按 Enter 跳過）：")

        age = input("年齡: ").strip()
        if age:
            patient_context["age"] = age

        gender = input("性別 (M/F/Other): ").strip()
        if gender:
            patient_context["gender"] = gender

        chief_complaint = input("主訴: ").strip()
        if chief_complaint:
            patient_context["chief_complaint"] = chief_complaint

        return {
            "transcript": transcript,
            "patient_context": patient_context if patient_context else None,
        }

    def process_transcript(
        self, transcript: str, patient_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """處理轉錄文字並生成 SOAP 病歷

        Args:
            transcript: 醫療對話轉錄文字
            patient_context: 病患背景資訊

        Returns:
            SOAP 病歷結果
        """
        if not self.generator:
            self.initialize()

        print("\n" + "=" * 60)
        print("處理中...")
        print("=" * 60)

        # 顯示術語標準化結果
        try:
            normalized_text, term_mappings = self.terminology_mapper.map_text(transcript)
            if term_mappings:
                print("\n📋 術語標準化結果:")
                for mapping in term_mappings:
                    icd10_str = (
                        f" ({', '.join(mapping.icd10_candidates)})"
                        if mapping.icd10_candidates
                        else ""
                    )
                    print(f"  • {mapping.original} → {mapping.standard}{icd10_str}")
        except Exception as e:
            logger.warning(f"術語標準化失敗: {e}")

        # 生成 SOAP 病歷
        try:
            if not self.generator:
                raise RuntimeError("SOAP 生成器未初始化")
            result = self.generator.generate(transcript, patient_context)
            return result
        except Exception as e:
            logger.error(f"SOAP 生成失敗: {e}")
            print(f"❌ SOAP 生成失敗: {e}")
            sys.exit(1)

    def display_result(self, result: Dict[str, Any]) -> None:
        """顯示 SOAP 病歷結果

        Args:
            result: SOAP 生成結果
        """
        print("\n" + "=" * 60)
        print("✅ SOAP 病歷生成完成")
        print("=" * 60)

        # 顯示 SOAP 各段落
        print("\n📝 SOAP 病歷:")
        print("-" * 40)

        if result.get("subjective"):
            print("S (主觀陳述):")
            print(result["subjective"])
            print()

        if result.get("objective"):
            print("O (客觀發現):")
            print(result["objective"])
            print()

        if result.get("assessment"):
            print("A (評估):")
            print(result["assessment"])
            print()

        if result.get("plan"):
            print("P (計畫):")
            print(result["plan"])
            print()

        if result.get("conversation_summary"):
            print("💬 對話摘要 (繁體中文):")
            print(result["conversation_summary"])
            print()

        # 顯示術語標準化結果
        if result.get("normalized_terms"):
            print("🔍 術語標準化:")
            for term in result["normalized_terms"]:
                icd10_str = (
                    f" ({', '.join(term['icd10_candidates'])})"
                    if term.get("icd10_candidates")
                    else ""
                )
                print(f"  • {term['original']} → {term['standard']}{icd10_str}")

        # 顯示病例範本檢索結果（RAG）
        case_templates = result.get("case_templates", [])
        if case_templates:
            print("\n📚 參考病例範本 (RAG 檢索):")
            for i, ct in enumerate(case_templates, 1):
                specialty = ct.get("specialty", "一般")
                rank = ct.get("rank", i)
                content = ct.get("content", "")[:150]
                if len(content) >= 150:
                    content = content[:150] + "..."
                print(f"  [{i}] {specialty} (排名 #{rank})")
                print(f"      {content}")
            print()

        # 顯示分類置信度
        if result.get("classification_confidence"):
            print("📊 分類置信度:")
            for category, confidence in result["classification_confidence"].items():
                bar = "█" * int(confidence * 20) + "░" * (20 - int(confidence * 20))
                print(f"  {category.upper():12s} {bar} {confidence:.1%}")

        print("\n" + "=" * 60)

    def run_interactive(self) -> None:
        """執行互動式 CLI"""
        self.initialize()

        while True:
            try:
                # 獲取輸入
                inputs = self.interactive_input()

                # 處理並生成 SOAP
                result = self.process_transcript(inputs["transcript"], inputs["patient_context"])

                # 顯示結果
                self.display_result(result)

                # 詢問是否繼續
                print("\n是否繼續處理另一筆對話？ (y/n): ", end="")
                choice = input().strip().lower()
                if choice not in ["y", "yes", "是"]:
                    print("\n感謝使用 SoapVoice！")
                    break

            except KeyboardInterrupt:
                print("\n\n操作取消")
                break
            except Exception as e:
                logger.error(f"執行錯誤: {e}")
                print(f"❌ 發生錯誤: {e}")
                print("是否重試？ (y/n): ", end="")
                choice = input().strip().lower()
                if choice not in ["y", "yes", "是"]:
                    break


def main():
    """CLI 主函數"""
    parser = argparse.ArgumentParser(
        description="SoapVoice - 醫療語音轉 SOAP 病歷系統 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  %(prog)s                     # 互動式模式
  %(prog)s --model qwen3.5:27b # 使用備用模型
  %(prog)s --file input.txt    # 從檔案讀取對話
  %(prog)s --text "病人胸悶..." # 直接輸入對話文字
        """,
    )

    parser.add_argument(
        "--model", default="qwen2.5:14b", help="指定使用的 Ollama 模型 (預設: qwen2.5:14b)"
    )

    parser.add_argument(
        "--api-base",
        default="http://localhost:11434",
        help="Ollama API 基礎 URL (預設: http://localhost:11434)",
    )

    parser.add_argument(
        "--extended",
        "-e",
        action="store_true",
        help="使用擴展模式：包含症狀提取、ICD-10、醫囑建議、藥物建議",
    )

    parser.add_argument("--audio", "-a", help="音訊檔案路徑 (使用 Whisper 轉錄)")

    parser.add_argument("--file", help="從檔案讀取醫療對話內容")

    parser.add_argument("--text", help="直接輸入醫療對話文字")

    parser.add_argument("--age", help="病患年齡")

    parser.add_argument("--gender", help="病患性別 (M/F/Other)")

    parser.add_argument("--chief-complaint", help="病患主訴")

    parser.add_argument("--verbose", "-v", action="store_true", help="顯示詳細日誌")

    args = parser.parse_args()

    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler()],
    )

    # 建立配置
    config = SOAPConfig(model_id=args.model, api_base=args.api_base)

    # 處理擴展模式
    if args.extended or args.audio:
        from scripts.extended_soapvoice import ExtendedSoapVoiceEngine

        engine = ExtendedSoapVoiceEngine(llm_model=args.model)

        if args.audio:
            # 音訊模式：轉錄 + 完整流程
            print("🎙️ 使用擴展模式處理音訊...")
            result = engine.process(args.audio)

            print("\n" + "=" * 60)
            print("📋 擴展 SOAP 結果")
            print("=" * 60)

            print(f"\n🔍 症狀: {result.symptoms}")
            print(f"\n🏥 ICD-10: {[c['code'] for c in result.icd10_codes]}")
            print(f"\n📋 醫囑: {result.medical_orders}")
            print(f"\n💊 藥物: {[d['name'] for d in result.drug_recommendations]}")
            print(f"\n⏱️ 處理時間: {result.processing_time:.2f}s")
            print("\n📄 English SOAP:")
            print(result.soap_en)
            sys.exit(0)
        else:
            # 文字模式 + extended
            try:
                if args.file:
                    with open(args.file, "r", encoding="utf-8") as f:
                        transcript = f.read().strip()
                elif args.text:
                    transcript = args.text
                else:
                    print("❌ 請提供 --text 或 --file 輸入")
                    sys.exit(1)

                print("🔄 處理中...")

                # 執行擴展流程
                symptoms = engine.extract_symptoms(transcript)
                icd10 = engine.classify_icd10(transcript)
                orders = engine.get_medical_orders(symptoms, [c["code"] for c in icd10])
                drugs = engine.get_drug_recommendations(symptoms, [c["code"] for c in icd10])
                soap = engine.generate_extended_soap(transcript, symptoms, icd10, orders, drugs)

                print("\n" + "=" * 60)
                print("📋 擴展 SOAP 結果")
                print("=" * 60)

                print(f"\n🔍 症狀: {symptoms}")
                print(f"\n🏥 ICD-10: {[(c['code'], c['description']) for c in icd10]}")
                print(f"\n📋 醫囑: {orders}")
                print(f"\n💊 藥物: {[(d['name'], d['dosage']) for d in drugs]}")
                print("\n📄 English SOAP:")
                print(soap["en"])
                sys.exit(0)

            except Exception as e:
                print(f"❌ 擴展模式錯誤: {e}")
                sys.exit(1)

    cli = SoapVoiceCLI(config)

    # 處理不同輸入模式
    if args.file:
        # 檔案模式
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                transcript = f.read().strip()
        except Exception as e:
            print(f"❌ 讀取檔案失敗: {e}")
            sys.exit(1)

        patient_context = {}
        if args.age:
            patient_context["age"] = args.age
        if args.gender:
            patient_context["gender"] = args.gender
        if args.chief_complaint:
            patient_context["chief_complaint"] = args.chief_complaint

        cli.initialize()
        result = cli.process_transcript(transcript, patient_context or None)
        cli.display_result(result)

    elif args.text:
        # 文字模式
        transcript = args.text
        patient_context = {}
        if args.age:
            patient_context["age"] = args.age
        if args.gender:
            patient_context["gender"] = args.gender
        if args.chief_complaint:
            patient_context["chief_complaint"] = args.chief_complaint

        cli.initialize()
        result = cli.process_transcript(transcript, patient_context or None)
        cli.display_result(result)

    else:
        # 互動式模式
        cli.run_interactive()


if __name__ == "__main__":
    main()
