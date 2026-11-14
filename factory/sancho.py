#!/usr/bin/env python3
"""Runs the factory from anywhere: `python3 factory/sancho.py review --offline`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sancho.__main__ import main  # noqa: E402

sys.exit(main())
