"""CliVoice 主入口點"""

import sys
from .cli.main import cli

if __name__ == "__main__":
    sys.exit(cli())
