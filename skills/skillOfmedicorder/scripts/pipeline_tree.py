#!/usr/bin/env python3
"""
純舊版+Tree搜尋版 - 不使用Vector搜尋
"""

import pandas as pd
import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from optimized_hybrid_search import OptimizedHybridSearch

BASE_DIR = Path(__file__).parent.parent
CURRENT_DIR = BASE_DIR / "current"
OLD_CSV = CURRENT_DIR / "醫療服務給付項目251027準確板_已優化填入支付規定.csv"


def main():
    start = time.time()

    # 載入舊版規定
    print("載入舊版規定...")
    old_df = pd.read_csv(OLD_CSV, encoding="utf-8-sig")
    code_col = next(c for c in old_df.columns if "診療項目代碼" in c)
    old_regs = {}
    for _, row in old_df.iterrows():
        code = str(row[code_col]).strip()
        reg = str(row["支付規定"]).strip() if pd.notna(row["支付規定"]) else ""
        if reg and reg != "null":
            old_regs[code] = reg
    print(f"舊版載入 {len(old_regs)} 筆")

    # 讀取新CSV
    new_csv = CURRENT_DIR / "醫療服務給付項目及支付標準_1150316.csv"
    print(f"讀取 {new_csv.name}...")
    df = pd.read_csv(new_csv, encoding="utf-8-sig")
    code_col = next(c for c in df.columns if "診療項目代碼" in c)
    df = df.rename(columns={code_col: "診療項目代碼"})

    # 篩選C類
    mask = df["診療項目代碼"].astype(str).str.strip().str.endswith("C")
    df_c = df[mask].copy()
    print(f"C類項目：{len(df_c)} 筆")

    # 初始化搜尋器（只用Tree搜尋，不建立Vector索引）
    print("初始化Tree搜尋器...")
    searcher = OptimizedHybridSearch(
        tree_dir=str(BASE_DIR / "PageIndex/results"),
        doc_dir=str(BASE_DIR / "審查注意事項"),
    )

    # 填充規定
    df_c["支付規定"] = "null"
    nlm_needed = []
    used_old = 0
    used_tree = 0

    for i, (idx, row) in enumerate(df_c.iterrows()):
        code = str(row["診療項目代碼"]).strip()
        name = str(row.get("中文項目名稱", ""))

        # 1. 先用舊版
        if code in old_regs:
            df_c.at[idx, "支付規定"] = old_regs[code]
            used_old += 1
            continue

        # 2. 用Tree搜尋
        results = searcher.search(name, top_k=2, method="tree")
        if results:
            text = results[0].get("text", "")[:200]
            # 清理
            lines = [
                l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 3
            ]
            snippet = "；".join(lines[:3])[:50]
            df_c.at[idx, "支付規定"] = snippet
            used_tree += 1
            continue

        # 3. 空值
        try:
            points = (
                float(row["健保支付點數"]) if pd.notna(row.get("健保支付點數")) else 0
            )
        except:
            points = 0

        if points > 350:
            nlm_needed.append({"code": code, "name": name, "points": points})

        if (i + 1) % 500 == 0:
            print(f"進度: {i + 1}/{len(df_c)}")

    # 輸出
    output_path = CURRENT_DIR / f"醫療服務給付項目_{new_csv.stem}_C類_tree.csv"
    df_c.to_csv(output_path, index=False, encoding="utf-8-sig")

    elapsed = time.time() - start
    print(f"\n完成！")
    print(f"  輸出：{output_path.name}")
    print(f"  總筆數：{len(df_c)}")
    print(f"  使用舊版：{used_old} ({used_old / len(df_c) * 100:.1f}%)")
    print(f"  使用Tree：{used_tree} ({used_tree / len(df_c) * 100:.1f}%)")
    print(
        f"  空值：{len(df_c) - used_old - used_tree} ({(len(df_c) - used_old - used_tree) / len(df_c) * 100:.1f}%)"
    )
    print(f"  耗時：{elapsed:.1f} 秒")

    if nlm_needed:
        nlm_path = CURRENT_DIR / f"notebooklm_pending_{new_csv.stem}.json"
        with open(nlm_path, "w", encoding="utf-8") as f:
            json.dump(nlm_needed, f, ensure_ascii=False, indent=2)
        print(f"  NotebookLM待查：{len(nlm_needed)}筆")


if __name__ == "__main__":
    main()
