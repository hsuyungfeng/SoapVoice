#!/usr/bin/env python3
"""
CliVoice 使用範例
"""

import sys

sys.path.insert(0, ".")

from cli_anything.clivoice import cli, IntegrationOrchestrator, SOAPNote


def example_1_basic_usage():
    """基本使用範例"""
    print("=== 範例 1: 基本使用 ===")

    # 建立 SOAP 病歷
    soap_text = """
    主觀資料(S): 病人主訴咳嗽、發燒三天，喉嚨痛
    客觀資料(O): 體溫38.5°C，喉嚨紅腫，心跳每分鐘90次
    評估(A): 急性上呼吸道感染
    計畫(P): 給予退燒藥，建議休息多喝水，三天後回診
    """

    # 解析 SOAP 病歷
    soap_note = SOAPNote.from_text(soap_text)
    print(f"解析 SOAP 病歷: {soap_note.summary}")

    # 建立整合協調器
    orchestrator = IntegrationOrchestrator()

    # 處理 SOAP 病歷
    result = orchestrator.process_soap_note(soap_note)

    # 顯示結果
    print(f"\n診斷結果: {len(result.diagnoses)} 個診斷")
    for i, diagnosis in enumerate(result.diagnoses[:3], 1):
        print(f"  {i}. {diagnosis.code} - {diagnosis.name} ({diagnosis.confidence:.1%})")

    print(f"\n醫療訂單: {len(result.orders)} 個醫囑，總費用: {result.total_fee:.2f}")
    for i, order in enumerate(result.orders[:3], 1):
        print(f"  {i}. {order.code} - {order.name} ({order.category}, {order.fee:.2f})")

    print(f"\n藥物建議: {len(result.drug_recommendations)} 種藥物")
    for i, drug in enumerate(result.drug_recommendations[:3], 1):
        print(f"  {i}. {drug.code} - {drug.name} ({drug.form})")


def example_2_cli_usage():
    """CLI 使用範例"""
    print("\n=== 範例 2: CLI 使用 ===")
    print("安裝後可使用以下命令:")
    print("")
    print("1. 分析 SOAP 病歷:")
    print('   clivoice analyze "病人咳嗽發燒三天" --json')
    print("")
    print("2. 根據症狀查詢診斷:")
    print("   clivoice diagnose 咳嗽 --limit 5")
    print("")
    print("3. 查詢診斷相關醫囑:")
    print("   clivoice orders J06.9 --category 藥物")
    print("")
    print("4. 查詢診斷建議藥物:")
    print("   clivoice drugs J06.9 --atc-class N02")
    print("")
    print("5. 進入互動模式:")
    print("   clivoice repl")
    print("")
    print("6. 批次處理檔案:")
    print("   clivoice batch-process soap_notes.txt --output results.json")


def example_3_advanced_features():
    """進階功能範例"""
    print("\n=== 範例 3: 進階功能 ===")

    # 建立 SOAP 病歷
    soap_note = SOAPNote(
        subjective="胃痛、噁心、食慾不振",
        objective="上腹部壓痛，無發燒",
        assessment="急性胃炎",
        plan="給予胃藥，建議清淡飲食",
    )

    # 建立整合協調器
    orchestrator = IntegrationOrchestrator()

    # 處理並優化治療計畫
    result = orchestrator.process_soap_note(soap_note)

    # 優化治療計畫 (預算限制)
    optimized = orchestrator.optimize_treatment_plan(result, budget=500.0)

    print(f"原始醫囑: {len(result.orders)} 個，總費用: {result.total_fee:.2f}")
    print(f"優化醫囑: {len(optimized.orders)} 個，總費用: {optimized.total_fee:.2f}")

    # 生成不同格式報告
    print("\n報告格式:")
    print("1. 文字報告:")
    text_report = orchestrator.generate_report(result, "text")
    print(f"   長度: {len(text_report)} 字元")

    print("2. JSON 報告:")
    json_report = orchestrator.generate_report(result, "json")
    print(f"   長度: {len(json_report)} 字元")

    print("3. Markdown 報告:")
    md_report = orchestrator.generate_report(result, "markdown")
    print(f"   長度: {len(md_report)} 字元")


def example_4_integration_test():
    """整合測試範例"""
    print("\n=== 範例 4: 整合測試 ===")

    # 測試多個 SOAP 病歷
    soap_notes = [
        SOAPNote(
            subjective="咳嗽、流鼻水", objective="體溫正常", assessment="普通感冒", plan="多休息"
        ),
        SOAPNote(
            subjective="頭痛、發燒",
            objective="體溫39.0°C",
            assessment="流行性感冒",
            plan="給予退燒藥",
        ),
        SOAPNote(
            subjective="腹瀉、腹痛",
            objective="腹部柔軟",
            assessment="急性腸胃炎",
            plan="給予止瀉藥",
        ),
    ]

    orchestrator = IntegrationOrchestrator()
    results = orchestrator.process_batch(soap_notes)

    print(f"批次處理 {len(soap_notes)} 個病歷，成功 {len(results)} 個")

    for i, result in enumerate(results, 1):
        primary_diagnosis = result.diagnoses[0].name if result.diagnoses else "無診斷"
        print(f"  病歷 {i}: {primary_diagnosis} - {len(result.orders)} 醫囑")


if __name__ == "__main__":
    print("CliVoice 使用範例")
    print("=" * 60)

    example_1_basic_usage()
    example_2_cli_usage()
    example_3_advanced_features()
    example_4_integration_test()

    print("\n" + "=" * 60)
    print("範例執行完成！")
