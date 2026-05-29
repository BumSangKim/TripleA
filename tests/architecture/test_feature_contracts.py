"""
Feature 구조 계약 테스트.

검증 범위:
- api/features/ 없으면 전체 skip
- service.py에서 HTTPException, get_conn, sqlite3 import 금지
- repository.py에서 FastAPI import 금지
- service/repository class 존재 여부 검증
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
FEATURES_DIR = ROOT / "api" / "features"


def _has_class(filepath: Path) -> bool:
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    return any(isinstance(node, ast.ClassDef) for node in ast.walk(tree))


def _get_imports(filepath: Path) -> list[str]:
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            result.append(module)
            for alias in node.names:
                result.append(f"{module}.{alias.name}" if module else alias.name)
    return result


def _get_feature_dirs() -> list[Path]:
    if not FEATURES_DIR.exists():
        return []
    return [d for d in FEATURES_DIR.iterdir() if d.is_dir() and not d.name.startswith("_")]


pytestmark = pytest.mark.skipif(
    not FEATURES_DIR.exists(),
    reason="api/features/ 없음 — feature 마이그레이션 전. Task 006은 feature 디렉터리 생성 후 활성화.",
)


# ---------------------------------------------------------------------------
# service.py 계약
# ---------------------------------------------------------------------------


def test_service_no_http_exception():
    """feature service.py는 HTTPException을 import해서는 안 된다."""
    violations = []
    for feature_dir in _get_feature_dirs():
        service_file = feature_dir / "service.py"
        if not service_file.exists():
            continue
        source = service_file.read_text(encoding="utf-8")
        if "HTTPException" in source:
            violations.append(str(service_file.relative_to(ROOT)))
    assert not violations, (
        "service.py가 HTTPException을 import합니다:\n" + "\n".join(violations)
    )


def test_service_no_get_conn():
    """feature service.py는 get_conn을 직접 import해서는 안 된다."""
    violations = []
    for feature_dir in _get_feature_dirs():
        service_file = feature_dir / "service.py"
        if not service_file.exists():
            continue
        source = service_file.read_text(encoding="utf-8")
        if "get_conn" in source:
            violations.append(str(service_file.relative_to(ROOT)))
    assert not violations, (
        "service.py가 get_conn을 사용합니다:\n" + "\n".join(violations)
    )


def test_service_no_sqlite3():
    """feature service.py는 sqlite3를 직접 import해서는 안 된다."""
    violations = []
    for feature_dir in _get_feature_dirs():
        service_file = feature_dir / "service.py"
        if not service_file.exists():
            continue
        imports = _get_imports(service_file)
        if "sqlite3" in imports:
            violations.append(str(service_file.relative_to(ROOT)))
    assert not violations, (
        "service.py가 sqlite3를 import합니다:\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# repository.py 계약
# ---------------------------------------------------------------------------


def test_repository_no_fastapi():
    """feature repository.py는 FastAPI를 import해서는 안 된다."""
    violations = []
    for feature_dir in _get_feature_dirs():
        repo_file = feature_dir / "repository.py"
        if not repo_file.exists():
            continue
        source = repo_file.read_text(encoding="utf-8")
        if "fastapi" in source or "HTTPException" in source:
            violations.append(str(repo_file.relative_to(ROOT)))
    assert not violations, (
        "repository.py가 FastAPI를 import합니다:\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# class 존재 여부 계약
# ---------------------------------------------------------------------------


def test_service_has_class():
    """feature service.py는 최소 1개의 class를 포함해야 한다."""
    violations = []
    for feature_dir in _get_feature_dirs():
        service_file = feature_dir / "service.py"
        if not service_file.exists():
            continue
        if not _has_class(service_file):
            violations.append(str(service_file.relative_to(ROOT)))
    assert not violations, (
        "service.py에 class가 없습니다 (class-only 규칙):\n" + "\n".join(violations)
    )


def test_repository_has_class():
    """feature repository.py는 최소 1개의 class를 포함해야 한다."""
    violations = []
    for feature_dir in _get_feature_dirs():
        repo_file = feature_dir / "repository.py"
        if not repo_file.exists():
            continue
        if not _has_class(repo_file):
            violations.append(str(repo_file.relative_to(ROOT)))
    assert not violations, (
        "repository.py에 class가 없습니다 (class-only 규칙):\n" + "\n".join(violations)
    )
