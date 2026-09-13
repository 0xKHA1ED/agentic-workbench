#!/usr/bin/env python3
"""Entry point: python scripts/project_tree.py <command> <project> ..."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from project_tree.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
