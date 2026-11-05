"""The native head reader, shared with headkit (same results and refusals on every candidate compared 2026-11-04)."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from headkit.native_reader import decode  # noqa: E402,F401
