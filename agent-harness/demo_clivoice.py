#!/usr/bin/env python3
"""
CliVoice CLI 使用示範
"""

import sys
import json
from pathlib import Path

# 添加專案路徑到 sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cli_anything.clivoice.models.soap_note import SOAPNote
from cli_anything.clivoice.adapters.icd10_adapter import ICD10Adapter
from cli_anything.clivoice.adapters.medical_order_adapter import MedicalOrderAdapter
from cli_anything.clivoice.adapters.atc_drug_adapter import ATCDrugAdapter


def demo_1_basic_models():
    """示範基本資料模型"""
    print("=" * 60)
    print("示範 1: 基本資料模型")
    print("=" * 60)

    # 建立 SOAP 病歷
    soap_text = """
    主觀資料(S): 病人主訴咳嗽、發燒三天，喉嚨痛
    客觀資料(O): 體溫38.5°C，喉嚨紅腫
    評估(A): 急性上呼吸道感染
    計畫(P): 給予退燒藥，建議休息多喝水
    """

    soap_note = SOAPNote.from_text(soap_text)
    print(f"✓ SOAP 病歷解析完成")
    print(f"  主觀: {soap_note.subjective.content[:50]}...")
    print(f"  客觀: {soap_note.objective.content[:50]}...")
    print(f"  評估: {soap_note.assessment.content[:50]}...")
    print(f"  計畫: {soap_note.plan.content[:50]}...")
    print()


def demo_2_icd10_adapter():
    """示範 ICD-10 適配器"""
    print("=" * 60)
    print("示範 2: ICD-10 診斷查詢")
    print("=" * 60)

    adapter = ICD10Adapter()

    # 根據症狀查詢診斷
    symptoms = ["咳嗽", "發燒"]
    print(f"查詢症狀: {', '.join(symptoms)}")

    for symptom in symptoms:
        diagnoses = adapter.search_by_symptom(symptom)
        if diagnoses:
            print(f"\n{symptom} 的可能診斷:")
            for i, diagnosis in enumerate(diagnoses[:3], 1):
                print(f"  {i}. {diagnosis.icd10_code} - {diagnosis.name}")
                print(f"     信心度: {diagnosis.confidence:.1%}")
        else:
            print(f"\n{symptom}: 未找到診斷")
    print()


def demo_3_medical_orders():
    """示範醫療訂單查詢"""
    print("=" * 60)
    print("示範 3: 醫療訂單查詢")
    print("=" * 60)

    adapter = MedicalOrderAdapter()

    # 查詢診斷 J06.9 (急性上呼吸道感染) 的相關醫囑
    diagnosis_code = "J06.9"
    print(f"查詢診斷 {diagnosis_code} 的相關醫囑:")

    orders = adapter.get_orders_by_diagnosis(diagnosis_code)

    if orders:
        print(f"找到 {len(orders)} 個醫囑:")
        total_fee = 0.0
        for i, order in enumerate(orders, 1):
            print(f"  {i}. {order.code} - {order.name}")
            print(f"     類別: {order.category}")
            print(f"     費用: {order.fee:.2f}")
            if order.description:
                print(f"     描述: {order.description[:50]}...")
            total_fee += order.fee

        print(f"\n總費用: {total_fee:.2f}")
    else:
        print("未找到相關醫囑")
    print()


def demo_4_drug_recommendations():
    """示範藥物推薦"""
    print("=" * 60)
    print("示範 4: 藥物推薦查詢")
    print("=" * 60)

    adapter = ATCDrugAdapter()

    # 查詢診斷 J06.9 的建議藥物
    diagnosis_code = "J06.9"
    print(f"查詢診斷 {diagnosis_code} 的建議藥物:")

    drugs = adapter.get_drugs_by_diagnosis(diagnosis_code)

    if drugs:
        print(f"找到 {len(drugs)} 種建議藥物:")
        for i, drug in enumerate(drugs, 1):
            print(f"  {i}. {drug.code} - {drug.name}")
            print(f"     ATC 代碼: {drug.atc_code}")
            print(f"     劑型: {drug.form}")
            if drug.indications:
                print(f"     適應症: {drug.indications[:50]}...")
            if drug.dosage:
                print(f"     劑量: {drug.dosage[:50]}...")
    else:
        print("未找到建議藥物")
    print()


def demo_5_cli_commands():
    """示範 CLI 命令"""
    print("=" * 60)
    print("示範 5: CLI 命令使用方式")
    print("=" * 60)

    commands = [
        ("分析 SOAP 病歷", 'clivoice analyze "病人咳嗽發燒三天" --json'),
        ("根據症狀查詢診斷", "clivoice diagnose 咳嗽 --limit 5"),
        ("查詢診斷相關醫囑", "clivoice orders J06.9 --category 藥物"),
        ("查詢診斷建議藥物", "clivoice drugs J06.9 --atc-class N02"),
        ("批次處理檔案", "clivoice batch-process soap_notes.txt --output results.json"),
        ("進入互動模式", "clivoice repl"),
    ]

    print("安裝後可使用以下命令:\n")
    for description, command in commands:
        print(f"{description}:")
        print(f"  {command}\n")


def demo_6_integration_workflow():
    """示範完整整合流程"""
    print("=" * 60)
    print("示範 6: 完整醫療流程整合")
    print("=" * 60)

    print("CliVoice 整合三個醫療子系統的完整流程:")
    print()
    print("1. 📝 SOAP 病歷輸入")
    print("   → 病人主訴咳嗽、發燒三天")
    print()
    print("2. 🔍 症狀提取與診斷匹配")
    print("   → 提取症狀: 咳嗽、發燒")
    print("   → ICD10v2 診斷: J06.9 (急性上呼吸道感染)")
    print()
    print("3. 💊 醫療訂單生成")
    print("   → medicalordertreeview 醫囑:")
    print("     • 一般診察費 (150元)")
    print("     • 喉部檢查 (100元)")
    print("     • 感冒藥 (50元)")
    print()
    print("4. 🏥 藥物推薦")
    print("   → ATCcodeTW 建議藥物:")
    print("     • 乙醯胺酚 (退燒止痛)")
    print("     • 布洛芬 (消炎鎮痛)")
    print()
    print("5. 📊 整合輸出")
    print("   → 診斷報告")
    print("   → 治療計畫")
    print("   → 費用估算")
    print()


def main():
    """主函數"""
    print("🎯 CliVoice CLI Harness 使用示範")
    print("=" * 60)
    print()

    demo_1_basic_models()
    demo_2_icd10_adapter()
    demo_3_medical_orders()
    demo_4_drug_recommendations()
    demo_5_cli_commands()
    demo_6_integration_workflow()

    print("=" * 60)
    print("✅ 示範完成！")
    print()
    print("實際使用方式:")
    print("1. 安裝套件: pip install -e .")
    print("2. 執行命令: clivoice --help")
    print("3. 開始使用上述命令")
    print("=" * 60)


if __name__ == "__main__":
    main()
