#!/usr/bin/env python3
"""Entry point: python scripts/idea_assess.py <command> ..."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from idea_assess.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
