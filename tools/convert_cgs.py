#!/usr/bin/env python3
"""Wrapper to run convert_cgs from the workspace root tools/ directory."""
import sys
from pathlib import Path

# Add script/tools to path and delegate
SCRIPT_TOOLS = Path(__file__).resolve().parent.parent / "script" / "tools"
sys.path.insert(0, str(SCRIPT_TOOLS))

from convert_cgs import main

if __name__ == "__main__":
    sys.exit(main())

