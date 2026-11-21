#!/usr/bin/env python3
"""Launch Gradio UI from project root: python scripts/run_app.py"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web_ui.app import main

if __name__ == "__main__":
    main()
