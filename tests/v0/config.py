from pathlib import Path

TEST_FOLDER = Path(__file__).resolve().parent
ROOT = TEST_FOLDER.parent.parent

DOC_FOLDER = ROOT / "docs"
DOC_RULES = DOC_FOLDER / "artifacts" / "rules"
