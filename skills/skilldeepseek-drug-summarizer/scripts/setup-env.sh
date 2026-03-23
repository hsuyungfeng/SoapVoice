#!/bin/bash
# 環境設定載入工具 (互動式)
#
# 使用方式:
#   source scripts/setup-env.sh
#
# 此腳本會:
# 1. 檢查環境變數或 .env 檔案
# 2. 如果未設定，詢問您的 DeepSeek API 密鑰
# 3. 驗證必要的環境變數

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"
ENV_FILE="$PROJECT_ROOT/.env"

echo "🔧 環境設定工具"
echo "================================================================================"

# 方案 1: 檢查環境變數是否已設定
if [ ! -z "$DEEPSEEK_API_KEY" ]; then
    echo ""
    echo "✓ 從環境變數載入 DEEPSEEK_API_KEY"
    KEY_DISPLAY="${DEEPSEEK_API_KEY:0:5}...${DEEPSEEK_API_KEY: -5}"
    echo "   ✓ API密鑰: $KEY_DISPLAY"
else
    # 方案 2: 檢查 .env 檔案
    if [ -f "$ENV_FILE" ]; then
        echo ""
        echo "✓ 從 .env 檔案載入"
        set -a
        source "$ENV_FILE"
        set +a
    else
        # 方案 3: 互動式詢問
        echo ""
        echo "📝 需要輸入 DeepSeek API 密鑰"
        echo ""
        echo "   如何取得密鑰:"
        echo "   1. 訪問: https://platform.deepseek.com/api_keys"
        echo "   2. 登入您的 DeepSeek 帳號"
        echo "   3. 複製您的 API 密鑰 (格式: sk-xxxxxxxx)"
        echo ""

        read -sp "   請貼上您的 DeepSeek API 密鑰: " DEEPSEEK_API_KEY
        echo ""

        if [ -z "$DEEPSEEK_API_KEY" ]; then
            echo "❌ 錯誤: 未輸入密鑰"
            return 1
        fi

        # 詢問是否保存到 .env
        echo ""
        read -p "   💾 是否保存到 .env 檔案? (y/n, 預設: n): " save_choice

        if [[ "$save_choice" == "y" || "$save_choice" == "Y" ]]; then
            echo "DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY" > "$ENV_FILE"
            chmod 600 "$ENV_FILE"
            echo "   ✓ 已保存到 .env (權限: 600)"
        fi
    fi
fi

# 驗證必要變數
echo ""
echo "✓ 驗證環境變數:"

if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "   ❌ DEEPSEEK_API_KEY 未設定"
    return 1
else
    # 隱藏密鑰顯示 (只顯示前後幾字符)
    KEY_DISPLAY="${DEEPSEEK_API_KEY:0:5}...${DEEPSEEK_API_KEY: -5}"
    echo "   ✓ DEEPSEEK_API_KEY: $KEY_DISPLAY"
fi

# 驗證工作目錄
echo ""
echo "✓ 驗證工作目錄:"
echo "   PROJECT_ROOT: $PROJECT_ROOT"
echo "   SCRIPT_DIR: $SCRIPT_DIR"

# 檢查必要檔案
echo ""
echo "✓ 檢查輸入檔案:"

REQUIRED_FILES=(
    "健保用藥品項查詢項目檔_1150316.csv"
    "藥品項查詢項目檔251215 AI  摘要支付價大於0.csv"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$PROJECT_ROOT/$file" ]; then
        echo "   ✓ $file"
    else
        echo "   ⚠️  $file (未找到)"
    fi
done

# 建立必要目錄
echo ""
echo "✓ 建立工作目錄:"
mkdir -p "$PROJECT_ROOT/cache"
mkdir -p "$PROJECT_ROOT/cache/checkpoints"
echo "   ✓ cache/"
echo "   ✓ cache/checkpoints/"

echo ""
echo "================================================================================"
echo "✅ 環境設定完成!"
echo ""
echo "🚀 現在可以執行:"
echo "   bash scripts/00-run-all.sh"
echo ""
