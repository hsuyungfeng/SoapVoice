#!/usr/bin/env python3
"""
步驟 2-3: 比較找新藥並合併
1. 載入清洗後的 1150316
2. 載入舊版 251215
3. 找出新藥 (藥品代號不在251215中的)
4. 合併: 保留251215所有記錄 + 附加新藥
5. 儲存暫存檔
"""

import csv
from pathlib import Path

def main():
    print("=" * 80)
    print("步驟 2-3: 比較找新藥並合併")
    print("=" * 80)

    # 檔案名
    cleaned_1150316 = "健保用藥品項查詢項目檔_1150316.csv"
    old_251215 = "藥品項查詢項目檔251215 AI  摘要支付價大於0.csv"
    merged_output = "temp_merged_for_deepseek.csv"

    # 檢查輸入檔案
    if not Path(cleaned_1150316).exists():
        print(f"❌ 錯誤: 找不到 {cleaned_1150316}")
        return False

    if not Path(old_251215).exists():
        print(f"❌ 錯誤: 找不到 {old_251215}")
        return False

    print(f"\n📖 輸入檔案:")
    print(f"   ├─ 清洗後 1150316: {cleaned_1150316}")
    print(f"   └─ 舊版 251215: {old_251215}")

    # 步驟 2: 載入清洗後的1150316
    print(f"\n⏳ 步驟 2: 載入清洗後的1150316...")
    with open(cleaned_1150316, 'r', encoding='utf-8') as f:
        new_drugs_list = list(csv.DictReader(f))
    print(f"   ✓ 已載入: {len(new_drugs_list):,} 行")

    # 步驟 2: 載入舊版251215
    print(f"\n⏳ 步驟 2: 載入舊版251215...")
    with open(old_251215, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        all_251215 = list(reader)
    print(f"   ✓ 已載入: {len(all_251215):,} 行")
    print(f"   ✓ 欄位數: {len([f for f in fieldnames if f and f.strip()]):,} 個")

    # 建立舊版藥品代碼字典
    old_drugs_dict = {row['藥品代號'].strip(): row for row in all_251215}
    print(f"   ✓ 去重後: {len(old_drugs_dict):,} 個藥品")

    # 步驟 3: 找新藥
    print(f"\n⏳ 步驟 3: 比較找新藥...")

    # 定義共同欄位
    common_cols = [
        'ATC代碼', '分類分組名稱', '劑型', '單複方', '成分', '支付價',
        '有效起日', '有效迄日', '藥品中文名稱', '藥品代號', '藥品英文名稱',
        '藥商', '規格單位', '規格量', '藥品代碼超連結', '藥品分類'
    ]

    new_drugs = []
    for row in new_drugs_list:
        code = row.get('藥品代號', '').strip()
        if code and code not in old_drugs_dict:
            # 只取共同欄位
            new_row = {col: row.get(col, '') for col in fieldnames if col and col.strip()}
            new_drugs.append(new_row)

    print(f"   ✓ 找到新藥: {len(new_drugs):,} 個")

    if len(new_drugs) > 0:
        print(f"\n   樣本新藥 (前3個):")
        for i, drug in enumerate(new_drugs[:3], 1):
            code = drug.get('藥品代號', '')
            name = drug.get('藥品中文名稱', '')
            price = drug.get('支付價', '')
            print(f"   {i}. {code} - {name} (支付價: {price})")

    # 步驟 3: 合併
    print(f"\n⏳ 步驟 3: 合併資料集...")
    merged = all_251215 + new_drugs
    print(f"   ✓ 舊版記錄: {len(all_251215):,}")
    print(f"   ✓ 新藥記錄: {len(new_drugs):,}")
    print(f"   ✓ 合併後: {len(merged):,}")

    # 步驟 4: 保存暫存檔
    print(f"\n⏳ 步驟 4: 保存暫存檔...")
    valid_fields = [c for c in fieldnames if c and c.strip()]
    with open(merged_output, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=valid_fields)
        writer.writeheader()
        writer.writerows(merged)

    print(f"   ✓ 已保存: {merged_output}")
    print(f"   ✓ 行數: {len(merged):,}")
    print(f"   ✓ 編碼: UTF-8 (無BOM)")

    # 統計
    print(f"\n📊 合併統計:")
    print(f"   ├─ 舊版 (251215): {len(all_251215):,} 行")
    print(f"   ├─ 新藥 (1150316): {len(new_drugs):,} 行")
    print(f"   ├─ 合併後: {len(merged):,} 行")
    print(f"   └─ 新增比例: {100 * len(new_drugs) / len(merged):.1f}%")

    print("\n" + "=" * 80)
    print("✅ 步驟 2-3 完成")
    print("=" * 80)
    print("\n下一步: python3 scripts/03-rewash-merged.py")

    return True

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
