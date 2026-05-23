from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PANEL_DIR = ROOT / "panel"

for path in (ROOT, PANEL_DIR):
    path_s = str(path)
    if path_s not in sys.path:
        sys.path.insert(0, path_s)
