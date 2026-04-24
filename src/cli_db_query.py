#!/usr/bin/env python3
"""
Database Query CLI Tool for LLM Integration

提供命令列工具供 LLM 或外部應用查詢臨床資料庫
Support ICD-10, Medications, Medical Orders

使用方式：
    python -m src.cli_db_query query_icd10 "chest pain"
    python -m src.cli_db_query query_drugs "aspirin"
    python -m src.cli_db_query query_drugs_by_atc "N02"
    python -m src.cli_db_query query_medical_orders "injection"
    python -m src.cli_db_query get_icd10_details "R07.9"
    python -m src.cli_db_query get_stats
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional

# 添加專案根目錄到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.llm_db_cli import create_llm_db_cli


def parse_args() -> argparse.Namespace:
    """解析命令行參數"""
    parser = argparse.ArgumentParser(
        description="Database Query CLI Tool for SoapVoice",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cli_db_query query_icd10 "chest pain"
  python -m src.cli_db_query query_drugs "paracetamol"
  python -m src.cli_db_query query_drugs_by_atc "N02"
  python -m src.cli_db_query query_medical_orders "X-ray"
  python -m src.cli_db_query get_icd10_details "R07.9"
  python -m src.cli_db_query get_stats
        """
    )

    parser.add_argument(
        "command",
        help="Command to execute",
        choices=[
            "query_icd10",
            "query_drugs",
            "query_drugs_by_atc",
            "query_medical_orders",
            "get_icd10_details",
            "get_stats"
        ]
    )

    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Query string or code"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum results (default: 5)"
    )

    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/local_db/medical.db"),
        help="Database path (default: data/local_db/medical.db)"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    return parser.parse_args()


def format_result(result: dict, as_json: bool = False) -> str:
    """格式化結果"""
    if as_json:
        return json.dumps(result, ensure_ascii=False, indent=2)

    # 人類可讀格式
    lines = []

    if result.get("status") == "error":
        lines.append(f"❌ Error: {result.get('message', 'Unknown error')}")
        return "\n".join(lines)

    if result.get("status") == "not_found":
        lines.append(f"⚠️  Not found: {result.get('message', 'No results')}")
        return "\n".join(lines)

    if result.get("status") != "success":
        lines.append(f"⚠️  Status: {result.get('status', 'Unknown')}")
        return "\n".join(lines)

    # Success 狀態
    if "count" in result:
        lines.append(f"✅ Results: {result['count']} found\n")

    if "results" in result:
        for item in result["results"]:
            if "code" in item and "name_en" in item:
                # ICD-10 結果
                lines.append(f"  {item['code']}")
                lines.append(f"    English: {item['name_en']}")
                if "name_cn" in item:
                    lines.append(f"    Chinese: {item['name_cn']}")
                if "category" in item:
                    lines.append(f"    Category: {item['category']}")

            elif "drug_name_en" in item:
                # 藥品結果
                lines.append(f"  {item['drug_name_en']}")
                lines.append(f"    Chinese: {item['drug_name_cn']}")
                lines.append(f"    ATC: {item.get('atc_code', 'N/A')}")
                lines.append(f"    Form: {item.get('dosage_form', 'N/A')}")
                if "payment_price" in item and item["payment_price"]:
                    lines.append(f"    Price: ${item['payment_price']}")

            elif "name_en" in item and "order_code" in item:
                # 醫療服務結果
                lines.append(f"  {item['name_en']}")
                lines.append(f"    Chinese: {item['name_cn']}")
                lines.append(f"    Category: {item.get('category', 'N/A')}")
                lines.append(f"    Fee Points: {item.get('fee_points', 'N/A')}")

            lines.append("")

    elif "statistics" in result:
        # 統計資訊
        lines.append("Database Statistics:\n")
        for table, count in result["statistics"].items():
            lines.append(f"  {table}: {count:,} records")

    return "\n".join(lines)


def main():
    """主函式"""
    args = parse_args()

    # 初始化 CLI
    try:
        cli = create_llm_db_cli(args.db_path)
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        # 執行相應的命令
        if args.command == "query_icd10":
            if not args.query:
                print("❌ Error: query required for query_icd10", file=sys.stderr)
                sys.exit(1)
            result = cli.query_icd10(args.query, limit=args.limit)

        elif args.command == "query_drugs":
            if not args.query:
                print("❌ Error: query required for query_drugs", file=sys.stderr)
                sys.exit(1)
            result = cli.query_drugs(args.query, limit=args.limit)

        elif args.command == "query_drugs_by_atc":
            if not args.query:
                print("❌ Error: ATC code required for query_drugs_by_atc", file=sys.stderr)
                sys.exit(1)
            result = cli.query_drugs_by_atc(args.query, limit=args.limit)

        elif args.command == "query_medical_orders":
            if not args.query:
                print("❌ Error: query required for query_medical_orders", file=sys.stderr)
                sys.exit(1)
            result = cli.query_medical_orders(args.query, limit=args.limit)

        elif args.command == "get_icd10_details":
            if not args.query:
                print("❌ Error: ICD-10 code required", file=sys.stderr)
                sys.exit(1)
            result = cli.get_icd10_by_code(args.query)

        elif args.command == "get_stats":
            result = cli.get_statistics()

        else:
            print(f"❌ Unknown command: {args.command}", file=sys.stderr)
            sys.exit(1)

        # 輸出結果
        print(format_result(result, args.json))

    finally:
        cli.close()


if __name__ == "__main__":
    main()
