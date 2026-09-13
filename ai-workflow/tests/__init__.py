"""Test suite for ai-workflow."""

import sys
from pathlib import Path

# Ensure ai-workflow/scripts is discoverable when importing project_tree
SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
