#!/usr/bin/env python3
"""Evaluate the frozen presentation 872 questions with batched CUDA PyTorch."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.model.evaluate_boku_composition_torch import main  # noqa: E402

if __name__ == "__main__":
    main()
