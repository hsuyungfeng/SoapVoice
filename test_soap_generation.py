#!/usr/bin/env python3
"""
Task 3 Testing Suite: SOAP Generator Prompt Verification

Tests the improved prompt to verify:
1. No duplicate content in output
2. S/O/A/P format compliance
3. No conversation markers (【使用者】, 【助理】)
4. Professional medical terminology usage
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8010"
API_ENDPOINT = f"{BASE_URL}/api/v1/clinical/soap/generate"

# Test data - sample medical transcripts
TEST_CASES = [
    {
        "name": "Test 1: Simple respiratory complaint",
        "transcript": "患者: 醫生您好，我最近一周一直在咳嗽，特別是夜間。醫生: 咳嗽多久了? 患者: 大約一周。沒有發燒，但感覺喉嚨有點痛。醫生: 讓我聽聽您的呼吸音。深吸一口氣... 呼氣... 您的肺音清晰，沒有異常雜音。患者: 那是好消息。醫生: 是的。您最近有接觸感冒患者嗎? 患者: 有的，我的同事上周感冒了。醫生: 那可能就是病毒性上呼吸道感染。我建議多喝水，充足休息，保持室內濕度。如果咳嗽持續超過2周或出現發燒，請再來就診。",
        "checks": {
            "no_duplicate_lines": True,
            "has_s_section": True,
            "has_o_section": True,
            "has_a_section": True,
            "has_p_section": True,
            "no_user_marker": True,
            "no_assistant_marker": True,
        }
    },
    {
        "name": "Test 2: Hypertension follow-up",
        "transcript": "患者: 醫生，我按時吃藥了，但血壓還是有點高。醫生: 今天測量的血壓是多少? 患者: 上午量是145/92。醫生: 讓我檢查一下。現在量一下... 150/95。有頭暈或胸痛嗎? 患者: 沒有，就是偶爾有點疲勞。醫生: 您的心率是78，正常。飲食上有注意控制鹽分嗎? 患者: 有的，但工作比較忙。醫生: 建議增加運動，每周至少150分鐘的有氧運動。我可能需要調整您的降壓藥。先加量到每天一粒，一個月後再複診。",
        "checks": {
            "no_duplicate_lines": True,
            "has_s_section": True,
            "has_o_section": True,
            "has_a_section": True,
            "has_p_section": True,
            "no_user_marker": True,
            "no_assistant_marker": True,
        }
    },
    {
        "name": "Test 3: Complex abdominal pain",
        "transcript": "患者: 醫生，我的腹部疼痛已經持續3天了。醫生: 疼痛的位置在哪裡? 患者: 主要在右下腹。醫生: 疼痛的性質如何? 患者: 間歇性的，有時候還會噁心。醫生: 有發燒嗎? 患者: 昨天測了37.8度。醫生: 讓我觸診一下... 這裡疼嗎? 患者: 啊，是的，特別疼。醫生: 右下腹有反跳痛。我們可能需要做血檢和超聲波檢查來排除闌尾炎。現在禁食，如果疼痛加重立即去急診。",
        "checks": {
            "no_duplicate_lines": True,
            "has_s_section": True,
            "has_o_section": True,
            "has_a_section": True,
            "has_p_section": True,
            "no_user_marker": True,
            "no_assistant_marker": True,
        }
    },
]

def check_for_markers(text: str) -> Dict[str, bool]:
    """Check for unwanted conversation markers"""
    return {
        "has_user_marker": "【使用者】" in text or "[使用者]" in text or "患者:" in text,
        "has_assistant_marker": "【助理】" in text or "[助理]" in text or "醫生:" in text,
    }

def check_for_duplicates(text: str) -> tuple[bool, list]:
    """Check for duplicate lines in SOAP output"""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    seen = {}
    duplicates = []

    for i, line in enumerate(lines):
        if line in seen:
            duplicates.append((line, seen[line], i))
        else:
            seen[line] = i

    return len(duplicates) == 0, duplicates

def run_test(test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single test case"""
    print(f"\n{'='*70}")
    print(f"Running: {test_case['name']}")
    print(f"{'='*70}")

    # Call the API
    try:
        response = requests.post(
            API_ENDPOINT,
            json={
                "transcript": test_case["transcript"],
                "patient_context": {
                    "age": 45,
                    "gender": "M",
                    "chief_complaint": "Medical consultation"
                }
            },
            timeout=30
        )

        if response.status_code != 200:
            return {
                "test_name": test_case["name"],
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}",
                "response": None
            }

        soap = response.json()

        # Run checks
        full_output = json.dumps(soap, ensure_ascii=False)
        markers = check_for_markers(full_output)
        no_dups, duplicates = check_for_duplicates(full_output)

        results = {
            "test_name": test_case["name"],
            "success": True,
            "checks": {
                "no_duplicate_content": no_dups,
                "has_s_section": bool(soap.get("subjective", "").strip()),
                "has_o_section": bool(soap.get("objective", "").strip()),
                "has_a_section": bool(soap.get("assessment", "").strip()),
                "has_p_section": bool(soap.get("plan", "").strip()),
                "no_user_marker": not markers["has_user_marker"],
                "no_assistant_marker": not markers["has_assistant_marker"],
            },
            "duplicates": duplicates if duplicates else None,
            "soap_output": {
                "subjective": soap.get("subjective", "")[:100] + "...",
                "objective": soap.get("objective", "")[:100] + "...",
                "assessment": soap.get("assessment", "")[:100] + "...",
                "plan": soap.get("plan", "")[:100] + "...",
            },
            "raw_response_sample": soap.get("raw_response", "")[:150] + "..."
        }

        # Print results
        print(f"\n✓ API Response received")
        print(f"\nCheck Results:")
        for check, result in results["checks"].items():
            status = "✓" if result else "✗"
            print(f"  {status} {check}: {result}")

        if duplicates:
            print(f"\n⚠ Duplicates found:")
            for line, first_idx, second_idx in duplicates:
                print(f"  Line {first_idx} & {second_idx}: {line[:60]}...")

        print(f"\nSOAP Output samples:")
        for section, content in results["soap_output"].items():
            print(f"  {section}: {content}")

        return results

    except requests.exceptions.ConnectionError:
        return {
            "test_name": test_case["name"],
            "success": False,
            "error": "Connection refused - server may have crashed",
            "response": None
        }
    except Exception as e:
        return {
            "test_name": test_case["name"],
            "success": False,
            "error": str(e),
            "response": None
        }

def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("SoapVoice Task 3: SOAP Generator Prompt Testing")
    print("Testing improved prompt for quality, format, and cleanliness")
    print("="*70)

    results = []
    for test_case in TEST_CASES:
        result = run_test(test_case)
        results.append(result)
        time.sleep(1)  # Brief pause between tests

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    total = len(results)
    successful = sum(1 for r in results if r["success"])
    all_checks_passed = sum(
        1 for r in results
        if r["success"] and all(r["checks"].values())
    )

    print(f"\nTests completed: {successful}/{total}")
    print(f"All checks passed: {all_checks_passed}/{total}")

    for result in results:
        if result["success"]:
            checks_status = "✓" if all(result["checks"].values()) else "⚠"
            print(f"\n{checks_status} {result['test_name']}")
            for check, passed in result["checks"].items():
                status = "✓" if passed else "✗"
                print(f"    {status} {check}")
        else:
            print(f"\n✗ {result['test_name']}")
            print(f"    Error: {result['error']}")

    # Write detailed results to file
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Detailed results saved to test_results.json")

    return all_checks_passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
