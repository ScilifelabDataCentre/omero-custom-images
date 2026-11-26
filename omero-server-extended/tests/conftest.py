"""Make scripts/scilifelab importable in tests without an OMERO install."""

import sys
from pathlib import Path

# Do not write __pycache__ next to the script; the Dockerfile copies the whole
# scripts/ folder into the image.
sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "scilifelab"
sys.path.insert(0, str(SCRIPT_DIR))
