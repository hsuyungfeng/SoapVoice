"""
測試 SOAP 生成器模組
"""

import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_soap_generator_import():
    """測試 SOAPGenerator 導入與初始化"""
    try:
        from src.soap.soap_generator import SOAPGenerator, SOAPConfig

        # 建立配置（使用預設模型）
        config = SOAPConfig(model_id="qwen2.5:7b")
        generator = SOAPGenerator(config)
        assert generator is not None
        print("✅ SOAPGenerator 導入與初始化成功")
        return True
    except ImportError as e:
        print(f"❌ SOAPGenerator 導入失敗: {e}")
        return False
    except Exception as e:
        print(f"❌ SOAPGenerator 初始化失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_soap_generator_structure():
    """測試 SOAP 生成器結構（不呼叫 LLM）"""
    try:
        from src.soap.soap_generator import SOAPGenerator, SOAPConfig

        config = SOAPConfig(model_id="qwen2.5:7b")
        generator = SOAPGenerator(config)

        # 測試內部方法（如分類症狀）
        # 我們只檢查方法存在
        assert hasattr(generator, "generate"), "SOAPGenerator 缺少 generate 方法"
        assert hasattr(generator, "config"), "SOAPGenerator 缺少 config 屬性"

        print("✅ SOAPGenerator 結構測試通過")
        return True
    except Exception as e:
        print(f"❌ SOAPGenerator 結構測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("📄 測試 SOAP 生成器模組")
    print("=" * 60)

    if test_soap_generator_import() and test_soap_generator_structure():
        print("\n✅ SOAP 生成器模組測試通過")
        sys.exit(0)
    else:
        print("\n❌ SOAP 生成器模組測試失敗")
        sys.exit(1)
