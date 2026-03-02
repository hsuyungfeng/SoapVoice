"""
Pytest 配置檔案

設定測試環境與路徑
"""

import sys
from pathlib import Path

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
