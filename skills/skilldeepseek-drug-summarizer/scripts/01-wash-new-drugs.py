#!/usr/bin/env python3
"""
步驟 1: 清洗新藥CSV
清理 健保用藥品項查詢項目檔_1150316.csv
規則:
  - 支付價 >= 0
  - 有效迄日 == 9991231 (永久)
  - 有效起日在5年內 (ROC 114年 = 2025年)
  - 去重複: 藥品代號重複時保留最新有效起日
"""

import sys
from pathlib import Path

# 添加項目目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from drug_cleaner import clean_drug_data

def main():
    print("=" * 80)
    print("步驟 1: 清洗新藥CSV")
    print("=" * 80)

    input_file = "健保用藥品項查詢項目檔_1150316.csv"

    # 檢查輸入檔案
    if not Path(input_file).exists():
        print(f"❌ 錯誤: 找不到 {input_file}")
        print("   請確保 1150316 檔案在當前目錄")
        return False

    print(f"\n📖 輸入檔案: {input_file}")
    print(f"🔍 清洗規則:")
    print(f"   ├─ 支付價 >= 0")
    print(f"   ├─ 有效迄日 == 9991231 (永久)")
    print(f"   ├─ 有效起日在5年內 (ROC年 114)")
    print(f"   └─ 去重複: 保留最新有效起日")

    # 執行清洗
    print(f"\n⏳ 正在清洗...")
    result = clean_drug_data(input_file, today_roc_year=114)

    # 檢查結果
    if result.get("status") != "success":
        print(f"\n❌ 清洗失敗: {result.get('error', 'Unknown error')}")
        return False

    # 顯示統計
    print(f"\n✅ 清洗完成!")
    print(f"\n📊 統計:")
    print(f"   ├─ 原始行數: {result.get('original_rows', 'N/A'):,}")
    print(f"   ├─ 保留行數: {result.get('rows_kept', 0):,}")
    print(f"   ├─ 移除行數: {result.get('rows_deleted', 0):,}")
    print(f"   └─ 移除比例: {100 * result.get('rows_deleted', 0) / max(result.get('original_rows', 1), 1):.1f}%")

    if result.get('dedup_count', 0) > 0:
        print(f"\n🔄 去重複統計:")
        print(f"   └─ 移除重複: {result['dedup_count']:,} 筆")

    print(f"\n💾 輸出檔案: {input_file} (已覆蓋)")
    print(f"   └─ 編碼: UTF-8 (無BOM)")

    print("\n" + "=" * 80)
    print("✅ 步驟 1 完成")
    print("=" * 80)
    print("\n下一步: python3 scripts/02-merge-datasets.py")

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
