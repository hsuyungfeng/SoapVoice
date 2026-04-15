#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, ".")
os.environ["USE_LLAMA_CPP"] = "true"

from src.soap.soap_generator import SOAPGenerator, SOAPConfig

# 測試提示詞
config = SOAPConfig(model_id="qwen2.5:3b")
generator = SOAPGenerator(config)

# 測試對話
transcript = """醫師,我昨天開始胸口很悶呼吸不太順暢
這樣的情況持續多久了?有沒有發燒或咳嗽?
大概兩天了,沒有發燒但是走路快一點就會喘
之前有類似症狀嗎?有沒有心臟方面的病史?
沒有,但是我有抽菸大概抽了10年
好,我先幫你安排心電圖和胸部X光檢查
醫師,嚴重嗎?
目前先做檢查確認,你不要緊張"""

# 直接測試提示詞建構
from src.nlp.terminology_mapper import MedicalTerminologyMapper

mapper = MedicalTerminologyMapper()
normalized_text, term_mappings = mapper.map_text(transcript)
icd10_candidates = [
    code for m in term_mappings if m.icd10_candidates for code in m.icd10_candidates
]

prompt = generator._build_prompt(
    transcript=transcript,
    patient_context={"age": "45", "gender": "male"},
    normalized_text=normalized_text,
    term_mappings=term_mappings,
    icd10_candidates=icd10_candidates,
    case_templates=[],
    medical_orders=[],
    drug_recommendations=[],
)

print("=" * 80)
print("改進後的提示詞範例:")
print("=" * 80)
print(prompt)
print("=" * 80)

# 測試生成（可選，可能較慢）
print("\n測試 LLM 生成（可能需要時間）...")
try:
    result = generator.generate(transcript)
    print("\n生成的 SOAP 病歷:")
    print(f"S: {result.get('subjective', '')[:100]}...")
    print(f"O: {result.get('objective', '')[:100]}...")
    print(f"A: {result.get('assessment', '')[:100]}...")
    print(f"P: {result.get('plan', '')[:100]}...")
    print(f"摘要: {result.get('conversation_summary', '')[:100]}...")
except Exception as e:
    print(f"生成錯誤: {e}")
