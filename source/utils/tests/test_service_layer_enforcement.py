"""Meta-test suite: one test case per project file enforcing service-layer access.

Every Python file outside the allowed zones must avoid direct model usage
(`.objects` or importing `*.models`). Tests are generated dynamically so the
failure output clearly names the offending file as the test class.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Iterable, List, Tuple

from django.test import SimpleTestCase


PROJECT_ROOT = Path(__file__).resolve().parents[2]  # points to `source/`

# Paths that may access models directly.
ALLOWED_PARTS = {"services", "migrations", "tests"}
ALLOWED_FILENAMES = {"models.py"}


def iter_project_python_files() -> Iterable[Path]:
    for root, _, files in os.walk(PROJECT_ROOT):
        for name in files:
            if name.endswith(".py"):
                yield Path(root) / name


def is_allowed(path: Path) -> bool:
    for part in path.parts:
        if part in ALLOWED_PARTS:
            return True
    return path.name in ALLOWED_FILENAMES


def find_orm_violations(file_path: Path) -> List[Tuple[int, str]]:
    source = file_path.read_text()
    lines = source.splitlines()
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    violations: List[Tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "objects":
            line = lines[node.lineno - 1] if 0 <= node.lineno - 1 < len(lines) else ""
            if "# service-guard: allow" in line:
                continue
            violations.append((node.lineno, "direct `.objects` access"))
    return violations


def _slug_from_path(rel_path: Path) -> str:
    return "_".join(rel_path.with_suffix("").parts)


def _build_test_class(file_path: Path):
    rel_path = file_path.relative_to(PROJECT_ROOT)
    slug = _slug_from_path(rel_path)

    class FileServiceLayerTest(SimpleTestCase):
        maxDiff = None

        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            cls._file_path = file_path
            cls._rel_path = rel_path

        def test_no_direct_model_access(self):
            if is_allowed(self._rel_path):
                self.skipTest("Allowed path for direct model access.")

            violations = find_orm_violations(self._file_path)
            if violations:
                formatted = "; ".join(
                    f"line {lineno}: {desc}" for lineno, desc in violations
                )
                self.fail(f"{self._rel_path} → {formatted}")

    FileServiceLayerTest.__name__ = f"ServiceLayer_{slug}"
    return FileServiceLayerTest


# Dynamically create a test class per file so failures point to the file.
for _path in iter_project_python_files():
    globals()[_build_test_class(_path).__name__] = _build_test_class(_path)


__all__ = [name for name in globals() if name.startswith("ServiceLayer_")]
