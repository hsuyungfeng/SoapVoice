#!/bin/bash
# 完整工作流: 從新藥CSV到最終260316檔案
#
# 使用方式:
#   bash scripts/00-run-all.sh
#
# 環境變數:
#   export DEEPSEEK_API_KEY='sk-xxxxxxxx'

set -e  # 遇到錯誤停止

echo ""
echo "================================================================================"
echo "台灣全民健保藥品資料庫季度更新 - 完整工作流"
echo "================================================================================"

# 載入環境設定
echo ""
echo "🔧 載入環境設定..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"
ENV_FILE="$PROJECT_ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ 錯誤: 找不到 .env 檔案"
    echo ""
    echo "📝 建立步驟:"
    echo "   1. 複製範例檔: cp .env.example .env"
    echo "   2. 編輯 .env: 填入您的 DEEPSEEK_API_KEY"
    echo "   3. 再次執行: bash scripts/00-run-all.sh"
    echo ""
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

# 檢查環境
echo ""
echo "✓ 檢查環境..."

if [ ! -f "$PROJECT_ROOT/健保用藥品項查詢項目檔_1150316.csv" ]; then
    echo "❌ 錯誤: 找不到 健保用藥品項查詢項目檔_1150316.csv"
    exit 1
fi

if [ ! -f "$PROJECT_ROOT/藥品項查詢項目檔251215 AI  摘要支付價大於0.csv" ]; then
    echo "❌ 錯誤: 找不到 藥品項查詢項目檔251215 AI  摘要支付價大於0.csv"
    exit 1
fi

if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "❌ 錯誤: DEEPSEEK_API_KEY 未從 .env 載入"
    exit 1
fi

echo "   ✓ 輸入檔案: 已找到"
echo "   ✓ API密鑰: 已設定 (${DEEPSEEK_API_KEY:0:5}...${DEEPSEEK_API_KEY: -5})"

# 建立快取目錄
mkdir -p cache checkpoints

# 步驟 1
echo ""
echo "================================================================================"
echo "步驟 1/5: 清洗新藥CSV"
echo "================================================================================"
python3 scripts/01-wash-new-drugs.py
if [ $? -ne 0 ]; then
    echo "❌ 步驟 1 失敗"
    exit 1
fi

# 步驟 2-3
echo ""
echo "================================================================================"
echo "步驟 2-3/5: 比較找新藥並合併"
echo "================================================================================"
python3 scripts/02-merge-datasets.py
if [ $? -ne 0 ]; then
    echo "❌ 步驟 2-3 失敗"
    exit 1
fi

# 步驟 4
echo ""
echo "================================================================================"
echo "步驟 4/5: 第二次清洗合併檔案"
echo "================================================================================"
python3 scripts/03-rewash-merged.py
if [ $? -ne 0 ]; then
    echo "❌ 步驟 4 失敗"
    exit 1
fi

# 步驟 5
echo ""
echo "================================================================================"
echo "步驟 5/5: DeepSeek API 豐富"
echo "================================================================================"
python3 scripts/04-deepseek-enrich.py
if [ $? -ne 0 ]; then
    echo "❌ 步驟 5 失敗"
    exit 1
fi

# 步驟 6-7
echo ""
echo "================================================================================"
echo "步驟 6-7/5: 合併豐富資料並保存"
echo "================================================================================"
python3 scripts/05-finalize-260316.py
if [ $? -ne 0 ]; then
    echo "❌ 步驟 6-7 失敗"
    exit 1
fi

# 完成
echo ""
echo "================================================================================"
echo "✅ 工作流完成!"
echo "================================================================================"
echo ""
echo "📊 最終結果:"
python3 << 'EOF'
import csv
from pathlib import Path
from datetime import datetime

today = datetime.now()
date_stamp = today.strftime("%y%m%d")
final_file = f"藥品項查詢項目檔{date_stamp} AI  摘要支付價大於0.csv"

if Path(final_file).exists():
    with open(final_file, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    with_ai_note = sum(1 for r in rows if r.get('AI-note', '').strip())
    total = len(rows)
    coverage = (with_ai_note / total * 100) if total > 0 else 0

    print(f"   ✓ 檔案: {final_file}")
    print(f"   ✓ 總藥品: {total:,}")
    print(f"   ✓ AI-note: {with_ai_note:,} ({coverage:.1f}%)")
    print(f"   ✓ 編碼: UTF-8")
else:
    print(f"❌ 找不到最終檔案")
EOF

echo ""
echo "🎉 準備就緒: 可供臨床系統或政策分析使用"
echo ""
