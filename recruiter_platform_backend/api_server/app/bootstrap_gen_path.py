"""Ensure generated `recruitment.v1` protos are importable (`from recruitment.v1 import ...`)."""

from __future__ import annotations

import sys
from pathlib import Path


def install_gen_path() -> None:
    gen_root = Path(__file__).resolve().parent / "gen"
    p = str(gen_root)
    if p not in sys.path:
        sys.path.insert(0, p)
