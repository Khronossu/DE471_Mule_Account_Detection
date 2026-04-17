"""
Reproducible pipeline runner.

Executes the two stages in order from the project root:
  1. scripts/mule_acc_data_gen.py     -> data_ver2/ver_2_data.xlsx
  2. scripts/feature_extractor.py     -> data_ver2/ver_2_data_with_features.xlsx

Seeds are fixed inside each script, so running this always produces identical output.

Usage:
    python run_pipeline.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGES = [
    ROOT / "scripts" / "mule_acc_data_gen.py",
    ROOT / "scripts" / "feature_extractor.py",
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
    print("\nPipeline complete. Output written to data_ver2/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
