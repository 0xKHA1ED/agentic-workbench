#!/usr/bin/env python3
"""Host-repo shim — delegates to ai-workflow/scripts/tree_server.py."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_TARGET = Path(__file__).resolve().parent.parent / "ai-workflow" / "scripts" / "tree_server.py"

if not _TARGET.exists():
    raise SystemExit(f"ai-workflow package not found at {_TARGET.parents[1]}")

sys.argv[0] = str(_TARGET)
runpy.run_path(str(_TARGET), run_name="__main__")
