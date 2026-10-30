"""Compatibility wrapper: validate.py now runs `memo_dat.py check`.

Usage: python validate.py [scene.json ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from memo.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["check"] + sys.argv[1:]))
