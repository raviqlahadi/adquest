#!/usr/bin/env python3
"""Backward-compat entry shim — the implementation lives in the adquest/ package.

Keeps the existing symlink workflow alive:
    ln -sf ~/projects/adquest/adquest.py ~/.local/bin/adquest
"""
import sys
from pathlib import Path

# Ensure the repo root is importable regardless of how we're invoked
# (direct, symlinked, or from another cwd).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from adquest.cli import main

if __name__ == "__main__":
    main()
