from pathlib import Path

from tests.config import ROOT


def test_no_spaces_in_sub_folders() -> None:
    name_by_location: dict[Path, str] = {}
    to_check = [ROOT / "cognite"]
    while to_check:
        current = to_check.pop()
        for path in current.iterdir():
            if path.is_dir():
                if path.name not in {"node_modules"}:
                    to_check.append(path)
                if " " in path.name:
                    name_by_location[path] = path.name
                    raise ValueError(f"Subfolder with spaces found: {path}")

    assert not name_by_location, f"Subfolders with spaces found: {name_by_location}"
