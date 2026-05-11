"""
Reproducible pipeline runner.

Executes all three stages in order from the project root:
  1. scripts/01_generate_data.py      -> data/raw/star_schema.xlsx
  2. scripts/02_extract_features.py   -> data/processed/transactions_with_features.xlsx
  3. scripts/03_build_obt.py          -> data/final/obt_final.xlsx

Seeds are fixed inside each script, so running this always produces identical output.

Usage:
    python run_pipeline.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGES = [
    ROOT / "scripts" / "01_generate_data.py",
    ROOT / "scripts" / "02_extract_features.py",
    ROOT / "scripts" / "03_build_obt.py",
]


def main() -> int:
    for script in STAGES:
        print(f"\n=== Running: {script.name} ===")
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
        )
        if result.returncode != 0:
            print(f"Stage failed: {script.name} (exit {result.returncode})")
            return result.returncode
    print("\nPipeline complete. Output written to data/final/obt_final.xlsx")
    return 0


if __name__ == "__main__":
    sys.exit(main())
