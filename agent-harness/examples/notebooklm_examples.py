#!/usr/bin/env python3
"""
NotebookLM 整合範例

展示如何使用 NotebookLM 適配器增強醫療資料庫搜尋
"""

from cli_anything.clivoice.adapters.notebooklm_adapter import NotebookLMAdapter, NotebookLMQuery
import json


def demo_basic_search():
    """基本搜尋示範"""
    print("=" * 60)
    print("範例 1: 基本症狀搜尋")
    print("=" * 60)

    adapter = NotebookLMAdapter()

    # 搜尋咳嗽相關診斷
    symptoms = "咳嗽、發燒、喉嚨痛"
    result = adapter.search_symptoms(symptoms, max_results=5)

    print(f"\n搜尋症狀: {symptoms}")
    print(f"\n找到 {len(result)} 個相關診斷:")
    for i, diagnosis in enumerate(result, 1):
        print(f"{i}. {diagnosis.get('content', 'N/A')}")
        print(f"   來源: {diagnosis.get('source', 'unknown')}")
        print(f"   信心分數: {diagnosis.get('confidence', 0):.2f}")
        print()


def demo_treatment_search():
    """治療方案搜尋示範"""
    print("=" * 60)
    print("範例 2: 治療方案搜尋")
    print("=" * 60)

    adapter = NotebookLMAdapter()

    # 搜尋感冒的治療方案
    diagnosis = "急性上呼吸道感染 (J06.9)"
    treatments = adapter.search_treatment_protocols(diagnosis, max_results=5)

    print(f"\n診斷: {diagnosis}")
    print(f"\n找到 {len(treatments)} 個治療方案:")
    for i, treatment in enumerate(treatments, 1):
        print(f"{i}. {treatment.get('content', 'N/A')}")
        print()


def demo_drug_search():
    """藥物建議搜尋示範"""
    print("=" * 60)
    print("範例 3: 藥物建議搜尋")
    print("=" * 60)

    adapter = NotebookLMAdapter()

    # 搜尋感冒的藥物建議
    diagnosis = "J06.9 急性上呼吸道感染"
    drugs = adapter.search_drug_recommendations(diagnosis, max_results=5)

    print(f"\n診斷: {diagnosis}")
    print(f"\n找到 {len(drugs)} 個藥物建議:")
    for i, drug in enumerate(drugs, 1):
        print(f"{i}. {drug.get('content', 'N/A')}")
        print()


def demo_enhanced_diagnosis():
    """增強診斷資訊示範"""
    print("=" * 60)
    print("範例 4: 增強診斷資訊")
    print("=" * 60)

    adapter = NotebookLMAdapter()

    # 增強流感診斷資訊
    enhanced = adapter.enhance_diagnosis("J11.1", "流感")

    print(f"\n診斷: {enhanced['name']} ({enhanced['code']})")
    print(f"整體信心分數: {enhanced['confidence']:.2f}")
    print("\n增強資訊:")
    print(f"  - 流行病學: {enhanced['enhanced_info']['epidemiology']}")
    print(f"  - 臨床特徵: {enhanced['enhanced_info']['clinical_features']}")
    print(f"  - 診斷標準: {enhanced['enhanced_info']['diagnostic_criteria']}")
    print(f"  - 預後: {enhanced['enhanced_info']['prognosis']}")
    print(f"\n證據摘要: {enhanced['enhanced_info']['evidence_summary']}")


def demo_complete_workflow():
    """完整工作流程示範"""
    print("=" * 60)
    print("範例 5: 完整臨床工作流程")
    print("=" * 60)

    adapter = NotebookLMAdapter()

    # 病人症狀
    symptoms = "咳嗽、發燒 38.5 度、全身酸痛、喉嚨痛"

    print(f"\n病人症狀: {symptoms}")

    # Step 1: 搜尋可能的診斷
    print("\n[步驟 1] 搜尋可能的診斷...")
    diagnoses = adapter.search_symptoms(symptoms, max_results=3)

    if diagnoses:
        primary_diagnosis = diagnoses[0].get("content", "未知")
        print(f"主要診斷: {primary_diagnosis}")

        # Step 2: 搜尋治療方案
        print("\n[步驟 2] 搜尋治療方案...")
        treatments = adapter.search_treatment_protocols(primary_diagnosis, max_results=3)
        print(f"找到 {len(treatments)} 個治療方案")

        # Step 3: 搜尋藥物建議
        print("\n[步驟 3] 搜尋藥物建議...")
        drugs = adapter.search_drug_recommendations(primary_diagnosis, max_results=3)
        print(f"找到 {len(drugs)} 個藥物建議")

        # Step 4: 增強診斷資訊
        print("\n[步驟 4] 增強診斷資訊...")
        enhanced = adapter.enhance_diagnosis("J11", primary_diagnosis)
        print(f"信心分數: {enhanced['confidence']:.2f}")

        print("\n" + "=" * 60)
        print("工作流程完成!")
        print("=" * 60)


def main():
    """主程式"""
    print("\n" + "=" * 60)
    print("CliVoice CLI - NotebookLM 整合範例")
    print("=" * 60 + "\n")

    # 執行所有示範
    try:
        demo_basic_search()
        input("\n按 Enter 鍵繼續...")

        demo_treatment_search()
        input("\n按 Enter 鍵繼續...")

        demo_drug_search()
        input("\n按 Enter 鍵繼續...")

        demo_enhanced_diagnosis()
        input("\n按 Enter 鍵繼續...")

        demo_complete_workflow()

    except KeyboardInterrupt:
        print("\n\n使用者中斷執行")
    except Exception as e:
        print(f"\n\n錯誤: {e}")
        print("請確認 NotebookLM MCP CLI 已正確安裝")


if __name__ == "__main__":
    main()
