#!/usr/bin/env python3
"""Entry point: python scripts/task_breakdown.py <command> ..."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from task_breakdown.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
