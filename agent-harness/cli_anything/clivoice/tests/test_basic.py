#!/usr/bin/env python3
"""
基本功能測試
"""

import sys
import json
from pathlib import Path

# 添加專案根目錄到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.clivoice.models import (
    Patient,
    PatientInfo,
    SOAPNote,
    SOAPSection,
    Diagnosis,
    DiagnosisResult,
    DiagnosisConfidence,
)


def test_patient_model():
    """測試病患模型"""
    print("🧪 測試病患模型...")

    # 建立病患資訊
    info = PatientInfo(
        age=45,
        gender="M",
        weight_kg=70.5,
        height_cm=175.0,
        allergies=["penicillin"],
        chronic_conditions=["hypertension"],
    )

    patient = Patient(
        patient_id="P001",
        name="張三",
        info=info,
        chief_complaint="胸悶兩天",
    )

    # 測試屬性
    assert patient.get_age() == 45
    assert patient.info.bmi is not None
    assert patient.info.bmi_category == "正常體重"
    assert "penicillin" in patient.info.allergies

    print("✅ 病患模型測試通過")
    return True


def test_soap_note_model():
    """測試 SOAP 病歷模型"""
    print("🧪 測試 SOAP 病歷模型...")

    soap_note = SOAPNote(
        subjective=SOAPSection(
            content="病人主訴胸悶兩天，呼吸困難，輕微咳嗽",
            keywords=["胸悶", "呼吸困難", "咳嗽"],
        ),
        objective=SOAPSection(
            content="體溫 37.2°C，血壓 130/85 mmHg，呼吸音粗",
            keywords=["體溫", "血壓", "呼吸音"],
        ),
        assessment=SOAPSection(
            content="急性支氣管炎可能性大",
            keywords=["急性支氣管炎"],
        ),
        plan=SOAPSection(
            content="支氣管擴張劑吸入治療，追蹤症狀",
            keywords=["支氣管擴張劑", "追蹤"],
        ),
    )

    # 測試屬性
    assert soap_note.total_word_count > 0
    assert soap_note.has_plan
    assert len(soap_note.extract_symptoms()) >= 3
    assert len(soap_note.extract_findings()) >= 2

    print("✅ SOAP 病歷模型測試通過")
    return True


def test_diagnosis_model():
    """測試診斷模型"""
    print("🧪 測試診斷模型...")

    diagnosis = Diagnosis(
        icd10_code="J20.9",
        name="急性支氣管炎",
        name_en="Acute bronchitis",
        confidence=0.85,
        symptoms=["咳嗽", "呼吸困難", "胸悶"],
        recommendations=["休息", "多喝水", "必要時使用支氣管擴張劑"],
        severity="中度",
    )

    # 測試屬性
    assert diagnosis.is_primary
    assert diagnosis.confidence_level == DiagnosisConfidence.HIGH
    assert diagnosis.formatted_code == "J20.9 - 急性支氣管炎"

    # 測試診斷結果
    result = DiagnosisResult(
        diagnoses=[diagnosis],
        source_text="病人胸悶兩天呼吸困難",
    )

    assert result.has_diagnoses
    assert len(result.primary_diagnoses) == 1
    assert result.get_by_code("J20.9") == diagnosis

    print("✅ 診斷模型測試通過")
    return True


def test_models_integration():
    """測試模型整合"""
    print("🧪 測試模型整合...")

    # 建立病患
    patient = Patient(
        info=PatientInfo(age=45, gender="M"),
        chief_complaint="胸悶呼吸困難",
    )

    # 建立 SOAP
    soap_note = SOAPNote.from_text(
        """
S: 病人胸悶兩天呼吸困難，輕微咳嗽
O: 體溫 37.2°C，呼吸音粗
A: 急性支氣管炎
P: 支氣管擴張劑治療
""",
        auto_parse=True,
    )

    # 建立診斷
    diagnosis = Diagnosis(
        icd10_code="J20.9",
        name="急性支氣管炎",
        confidence=0.85,
        symptoms=soap_note.extract_symptoms(),
    )

    result = DiagnosisResult(
        diagnoses=[diagnosis],
        patient_id=patient.patient_id,
    )

    # 測試序列化
    patient_dict = patient.to_dict()
    soap_dict = soap_note.to_dict()
    result_dict = result.to_dict()

    assert "calculated_age" in patient_dict
    assert "symptoms" in soap_dict
    assert "summary" in result_dict

    print("✅ 模型整合測試通過")
    return True


def main():
    """主測試函數"""
    print("=" * 60)
    print("CliVoice 基本功能測試")
    print("=" * 60)

    tests = [
        ("病患模型", test_patient_model),
        ("SOAP 病歷模型", test_soap_note_model),
        ("診斷模型", test_diagnosis_model),
        ("模型整合", test_models_integration),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} 測試異常: {e}")
            import traceback

            traceback.print_exc()
            results.append((test_name, False))

    # 顯示測試結果
    print("\n" + "=" * 60)
    print("測試結果摘要")
    print("=" * 60)

    passed = 0
    total = len(results)

    for test_name, success in results:
        status = "✅ 通過" if success else "❌ 失敗"
        print(f"{test_name:20s} {status}")
        if success:
            passed += 1

    print(f"\n總計: {passed}/{total} 項測試通過")

    if passed == total:
        print("\n🎉 所有基本功能測試通過！")
        print("\n專案結構:")
        print("  • 資料模型: Patient, SOAPNote, Diagnosis, MedicalOrder, DrugRecommendation")
        print("  • 核心引擎: DiagnosisEngine (診斷分析)")
        print("  • 適配器: ICD10Adapter, MedicalOrderAdapter, ATCDrugAdapter")
        print("  • CLI 介面: Click-based 命令列工具")
        print("  • 配置文件: YAML 格式配置管理")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 項測試失敗")
        return 1


if __name__ == "__main__":
    sys.exit(main())
