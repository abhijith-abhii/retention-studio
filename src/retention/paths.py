from pathlib import Path
import os

ROOT = Path(os.environ.get("RETENTION_HOME", Path(__file__).resolve().parents[2]))

def ensure_dirs(root=ROOT):
    for folder in ["data/raw", "data/processed", "data/training", "data/scoring", "artifacts", "reports", "var/runs"]:
        (root / folder).mkdir(parents=True, exist_ok=True)
