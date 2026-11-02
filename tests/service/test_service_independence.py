import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "quote_service"
THIRD_PARTY = {"fastapi", "uvicorn", "pydantic", "starlette", "httpx", "pytest"}


def _modules(package):
    return sorted(package.rglob("*.py"))


def _imported_roots(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


def test_service_source_never_imports_staywell():
    assert _modules(SERVICE)
    for path in _modules(SERVICE):
        assert "staywell" not in set(_imported_roots(path)), path


def test_service_import_does_not_load_staywell():
    code = (
        "import sys, pkgutil, importlib, quote_service\n"
        "for m in pkgutil.walk_packages(quote_service.__path__, 'quote_service.'):\n"
        "    importlib.import_module(m.name)\n"
        "bad = [m for m in sys.modules if m == 'staywell' or m.startswith('staywell.')]\n"
        "assert not bad, bad\n"
    )
    subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), check=True)


def test_service_has_no_float_literals_or_float_calls():
    for path in _modules(SERVICE):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            assert not (isinstance(node, ast.Constant) and isinstance(node.value, float)), (path, node.lineno)
            assert not (isinstance(node, ast.Name) and node.id == "float"), (path, node.lineno)


def test_legacy_package_stays_standard_library_only():
    for path in _modules(ROOT / "staywell"):
        assert not (set(_imported_roots(path)) & THIRD_PARTY), path


def test_direct_dependencies_are_pinned_exactly():
    lines = [
        line.strip()
        for line in (ROOT / "requirements-service.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert lines == [
        "fastapi==0.115.12",
        "uvicorn==0.34.2",
        "pydantic==2.11.5",
        "httpx==0.28.1",
        "pytest==8.3.5",
    ]


def test_runtime_is_python_39_or_newer():
    assert sys.version_info >= (3, 9)
