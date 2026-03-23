#!/usr/bin/env python3
"""
步驟 5: DeepSeek API 豐富
為新藥品生成 給付規定 + AI-note

環境變數:
  export DEEPSEEK_API_KEY='sk-xxxxxxxx'

參數:
  - update_mode: "fill_missing" (只填空值)
  - cost_limit: $100 (防止超支)
  - checkpoint_interval: 1000 (每1000行保存)
"""

import os
import sys
from pathlib import Path

# 添加項目目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from drug_summarizer import summarize_drugs

def main():
    print("=" * 80)
    print("步驟 5: DeepSeek API 豐富")
    print("=" * 80)

    # 檢查API密鑰
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("\n❌ 錯誤: DEEPSEEK_API_KEY 未設定")
        print("   設定方式: export DEEPSEEK_API_KEY='sk-xxxxxxxx'")
        return False

    print(f"\n✓ API密鑰: 已設定")

    # 檢查輸入檔案
    input_file = "temp_merged_for_deepseek.csv"
    if not Path(input_file).exists():
        print(f"\n❌ 錯誤: 找不到 {input_file}")
        print("   請先執行 scripts/03-rewash-merged.py")
        return False

    output_file = "cache/enrichment_new_drugs.csv"
    Path("cache").mkdir(exist_ok=True)

    print(f"\n📖 輸入檔案: {input_file}")
    print(f"💾 輸出檔案: {output_file}")

    # 豐富參數
    print(f"\n⚙️  豐富設定:")
    print(f"   ├─ 模式: fill_missing (只填空值)")
    print(f"   ├─ 成本限制: $100 (防止超支)")
    print(f"   ├─ 速率限制: 60 req/min")
    print(f"   ├─ 快取位置: cache/drug_summaries.db")
    print(f"   └─ 檢查點: 每1000行保存")

    print(f"\n⏳ 正在執行 DeepSeek 豐富...")
    print(f"   (可能耗時 10-20 分鐘，包括速率限制等待)")

    # 執行豐富
    result = summarize_drugs(
        csv_path=input_file,
        output_path=output_file,
        update_mode="fill_missing",
        cost_limit=100,
        checkpoint_interval=1000,
        api_key=api_key
    )

    # 檢查結果
    if result.get("status") != "success":
        print(f"\n❌ 豐富失敗: {result.get('error', 'Unknown error')}")
        return False

    # 顯示統計
    print(f"\n✅ DeepSeek 豐富完成!")
    print(f"\n📊 處理統計:")
    print(f"   ├─ 已處理: {result.get('rows_processed', 0):,} 行")
    print(f"   ├─ 失敗: {result.get('rows_failed', 0):,} 行")
    print(f"   ├─ 成本: ${result.get('total_cost', 0):.2f}")
    print(f"   └─ 平均成本/藥品: ${result.get('total_cost', 0) / max(result.get('rows_processed', 1), 1):.4f}")

    # 快取統計
    cache_stats = result.get('cache_stats', {})
    if cache_stats:
        print(f"\n💾 快取統計:")
        print(f"   ├─ 快取藥品: {cache_stats.get('cached_drugs', 0):,}")
        print(f"   ├─ 快取命中: {cache_stats.get('cache_hits', 0):,}")
        print(f"   └─ API成本: ${cache_stats.get('total_api_cost', 0):.2f}")

    print(f"\n💾 輸出檔案: {output_file}")

    print("\n" + "=" * 80)
    print("✅ 步驟 5 完成")
    print("=" * 80)
    print("\n下一步: python3 scripts/05-finalize-260316.py")

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
