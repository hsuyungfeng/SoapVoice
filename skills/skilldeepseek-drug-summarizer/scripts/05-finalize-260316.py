#!/usr/bin/env python3
"""
步驟 6-7: 合併豐富資料並帶日期標注保存
1. 載入 DeepSeek 豐富結果
2. 載入清洗後的合併檔
3. 左連結: 將 給付規定 + AI-note 合併回來
4. 帶 YYMMDD 日期標注保存為 260316 檔案
"""

import csv
from datetime import datetime
from pathlib import Path

def main():
    print("=" * 80)
    print("步驟 6-7: 合併豐富資料並保存")
    print("=" * 80)

    # 檔案名
    enrichment_file = "cache/enrichment_new_drugs.csv"
    merged_file = "temp_merged_for_deepseek.csv"

    # 檢查輸入檔案
    if not Path(enrichment_file).exists():
        print(f"\n❌ 錯誤: 找不到 {enrichment_file}")
        print("   請先執行 scripts/04-deepseek-enrich.py")
        return False

    if not Path(merged_file).exists():
        print(f"\n❌ 錯誤: 找不到 {merged_file}")
        print("   請先執行 scripts/03-rewash-merged.py")
        return False

    print(f"\n📖 輸入檔案:")
    print(f"   ├─ DeepSeek結果: {enrichment_file}")
    print(f"   └─ 清洗合併: {merged_file}")

    # 步驟 6: 載入豐富資料
    print(f"\n⏳ 步驟 6: 載入 DeepSeek 豐富結果...")
    enrichment_dict = {}
    with open(enrichment_file, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            drug_code = row.get('藥品代號', '').strip()
            enrichment_dict[drug_code] = {
                '給付規定': row.get('給付規定', ''),
                'AI-note': row.get('AI-note', '')
            }

    print(f"   ✓ 已載入: {len(enrichment_dict):,} 筆豐富資料")

    # 載入清洗後的合併檔
    print(f"\n⏳ 步驟 6: 載入清洗合併檔...")
    with open(merged_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        merged_rows = list(reader)

    print(f"   ✓ 已載入: {len(merged_rows):,} 行")

    # 步驟 6: 應用豐富 (左連結)
    print(f"\n⏳ 步驟 6: 應用豐富資料...")
    enriched_count = 0
    for row in merged_rows:
        drug_code = row.get('藥品代號', '').strip()
        if drug_code in enrichment_dict:
            enrich = enrichment_dict[drug_code]
            # 只在欄位為空時才填充 (fill_missing)
            if not row.get('給付規定', '').strip():
                row['給付規定'] = enrich['給付規定']
            if not row.get('AI-note', '').strip():
                row['AI-note'] = enrich['AI-note']
            enriched_count += 1

    print(f"   ✓ 已套用豐富: {enriched_count:,} 筆")

    # 統計AI-note覆蓋率
    with_ai_note = sum(1 for r in merged_rows if r.get('AI-note', '').strip())
    total = len(merged_rows)
    coverage = (with_ai_note / total * 100) if total > 0 else 0

    print(f"   ✓ AI-note覆蓋: {with_ai_note:,} / {total:,} ({coverage:.1f}%)")

    # 步驟 7: 帶日期標注保存
    print(f"\n⏳ 步驟 7: 帶日期標注保存...")
    today = datetime.now()
    date_stamp = today.strftime("%y%m%d")  # YYMMDD format
    final_file = f"藥品項查詢項目檔{date_stamp} AI  摘要支付價大於0.csv"

    with open(final_file, 'w', encoding='utf-8', newline='') as f:
        valid_fields = [c for c in fieldnames if c and c.strip()]
        writer = csv.DictWriter(f, fieldnames=valid_fields)
        writer.writeheader()
        writer.writerows(merged_rows)

    print(f"   ✓ 已保存: {final_file}")
    print(f"   ✓ 行數: {len(merged_rows):,}")
    print(f"   ✓ 編碼: UTF-8 (無BOM)")

    # 日期說明
    print(f"\n📅 日期標注說明:")
    print(f"   ├─ 檔案名: 藥品項查詢項目檔{date_stamp} AI  摘要支付價大於0.csv")
    print(f"   ├─ 日期: {today.strftime('%Y年%m月%d日')} (YYMMDD = {date_stamp})")
    print(f"   └─ 用途: 版本追蹤 (每季度自動更新)")

    # 最終統計
    print(f"\n📊 最終統計:")
    print(f"   ├─ 總藥品數: {total:,}")
    print(f"   ├─ 有 AI-note: {with_ai_note:,} ({coverage:.1f}%)")
    print(f"   ├─ 無 AI-note: {total - with_ai_note:,} ({100-coverage:.1f}%)")
    print(f"   └─ 支付價: > 0 (所有藥品)")

    print("\n" + "=" * 80)
    print("✅ 步驟 6-7 完成")
    print("=" * 80)
    print(f"\n✨ 工作流完成!")
    print(f"   最終檔案: {final_file}")
    print(f"   準備就緒: 可供臨床系統或政策分析使用")

    return True

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
