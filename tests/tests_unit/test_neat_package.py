import ast
from pathlib import Path

import cognite.neat


def test_legacy_not_imported() -> None:
    """Test that legacy module is not imported."""
    neat_root = Path(cognite.neat.__file__).parent
    v0_package = neat_root / "_v0"
    legacy_import = neat_root / "legacy.py"

    legacy_imports: list[tuple[Path, int, str]] = []
    for py_file in neat_root.rglob("*.py"):
        # Skip files within the _v0 package itself
        if v0_package in py_file.parents or py_file.parent == v0_package or py_file == legacy_import:
            continue
        relative_py_file = py_file.relative_to(neat_root.parent.parent)
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("cognite.neat._v0"):
                        legacy_imports.append((relative_py_file, node.lineno, f"import {alias.name}"))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("cognite.neat._v0") or module == "cognite.neat._v0":
                    names = ", ".join(alias.name for alias in node.names)
                    legacy_imports.append((relative_py_file, node.lineno, f"from {module} import {names}"))

    if legacy_imports:
        lines = [
            "Legacy module 'cognite.neat._v0' should not be imported outside of _v0 package:",
            "",
        ]
        for file_path, lineno, import_stmt in legacy_imports:
            lines.append(f"  {file_path.as_posix()}:{lineno}: {import_stmt}")
        error_msg = "\n".join(lines)
    else:
        error_msg = ""

    assert len(legacy_imports) == 0, error_msg
