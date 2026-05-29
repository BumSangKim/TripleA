"""
Architecture import contract tests.

활성화 시점:
- legacy_db_in_router: PHASE_01 이후 (api/intraday/router.py 리팩토링 완료 시)
- legacy_db_in_features: api/features/ 생성 후 즉시 활성화
- legacy_modes_in_features: api/features/ 생성 후 즉시 활성화
- legacy_kis_in_features: api/features/ 생성 후 즉시 활성화
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent


def _collect_imports(filepath: Path) -> list[str]:
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _files_with_import(directory: Path, pattern: str) -> list[Path]:
    matches = []
    for py_file in directory.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        if pattern in source:
            matches.append(py_file.relative_to(ROOT))
    return sorted(matches)


# ---------------------------------------------------------------------------
# 현재 상태 기록 테스트 (항상 통과 — 위반 목록을 출력용으로 수집)
# ---------------------------------------------------------------------------


def test_collect_legacy_db_imports_report():
    """api/db 의존 현황을 보고한다 (assert 없음 — 현황 기록용)."""
    violations = _files_with_import(ROOT / "api", "api.db")
    violations += _files_with_import(ROOT / "api", "from api.db")
    if violations:
        print(f"\n[legacy api.db violations] {len(violations)} files:")
        for v in violations:
            print(f"  {v}")


def test_collect_legacy_modes_imports_report():
    """api/modes 의존 현황을 보고한다 (assert 없음 — 현황 기록용)."""
    violations = _files_with_import(ROOT / "api", "from api.modes")
    violations += _files_with_import(ROOT / "api", "import api.modes")
    if violations:
        print(f"\n[legacy api.modes violations] {len(violations)} files:")
        for v in violations:
            print(f"  {v}")


def test_collect_legacy_kis_imports_report():
    """api/kis 의존 현황을 보고한다 (assert 없음 — 현황 기록용)."""
    violations = _files_with_import(ROOT / "api", "from api.kis")
    violations += _files_with_import(ROOT / "api", "import api.kis")
    if violations:
        print(f"\n[legacy api.kis violations] {len(violations)} files:")
        for v in violations:
            print(f"  {v}")


# ---------------------------------------------------------------------------
# 계약 강제 테스트 (api/features/ 생성 후부터 즉시 강제)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (ROOT / "api" / "features").exists(),
    reason="api/features/ 없음 — feature 마이그레이션 전",
)
def test_features_router_no_db_import():
    """feature router는 api.db를 직접 import해서는 안 된다."""
    features_dir = ROOT / "api" / "features"
    violations = []
    for router_file in features_dir.rglob("router.py"):
        if "__pycache__" in router_file.parts:
            continue
        source = router_file.read_text(encoding="utf-8")
        if "from api.db" in source or "import api.db" in source:
            violations.append(str(router_file.relative_to(ROOT)))
    assert not violations, (
        f"feature router가 api.db를 직접 import합니다:\n" + "\n".join(violations)
    )


@pytest.mark.skipif(
    not (ROOT / "api" / "features").exists(),
    reason="api/features/ 없음 — feature 마이그레이션 전",
)
def test_features_router_no_repository_import():
    """feature router는 repository를 직접 import해서는 안 된다."""
    features_dir = ROOT / "api" / "features"
    violations = []
    for router_file in features_dir.rglob("router.py"):
        if "__pycache__" in router_file.parts:
            continue
        source = router_file.read_text(encoding="utf-8")
        if "repository" in source and (
            "from api.features" in source or "import repository" in source
        ):
            imports = _collect_imports(router_file)
            repo_imports = [i for i in imports if i.endswith(".repository")]
            if repo_imports:
                violations.append(f"{router_file.relative_to(ROOT)}: {repo_imports}")
    assert not violations, (
        f"feature router가 repository를 직접 import합니다:\n" + "\n".join(violations)
    )


@pytest.mark.skipif(
    not (ROOT / "api" / "features").exists(),
    reason="api/features/ 없음 — feature 마이그레이션 전",
)
def test_features_service_no_http_imports():
    """feature service는 FastAPI/HTTPException을 직접 import해서는 안 된다."""
    features_dir = ROOT / "api" / "features"
    violations = []
    for service_file in features_dir.rglob("service.py"):
        if "__pycache__" in service_file.parts:
            continue
        source = service_file.read_text(encoding="utf-8")
        forbidden = ["HTTPException", "from fastapi", "import fastapi", "get_conn", "sqlite3"]
        found = [f for f in forbidden if f in source]
        if found:
            violations.append(f"{service_file.relative_to(ROOT)}: {found}")
    assert not violations, (
        f"feature service가 금지 심볼을 import합니다:\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# 즉시 강제 계약 (api/domain, api/core 대상 — 이번 phase에서 생성)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (ROOT / "api" / "domain").exists(),
    reason="api/domain/ 없음 — Task 010 완료 후 활성화",
)
def test_domain_no_fastapi_import():
    """api/domain은 FastAPI를 import해서는 안 된다."""
    domain_dir = ROOT / "api" / "domain"
    violations = []
    for py_file in domain_dir.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        source = py_file.read_text(encoding="utf-8")
        if "fastapi" in source or "HTTPException" in source:
            violations.append(str(py_file.relative_to(ROOT)))
    assert not violations, (
        f"api/domain이 FastAPI를 import합니다:\n" + "\n".join(violations)
    )


@pytest.mark.skipif(
    not (ROOT / "api" / "domain").exists(),
    reason="api/domain/ 없음 — Task 010 완료 후 활성화",
)
def test_domain_no_db_import():
    """api/domain은 sqlite3나 api.db를 import해서는 안 된다."""
    domain_dir = ROOT / "api" / "domain"
    violations = []
    for py_file in domain_dir.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        source = py_file.read_text(encoding="utf-8")
        if "sqlite3" in source or "from api.db" in source or "import api.db" in source:
            violations.append(str(py_file.relative_to(ROOT)))
    assert not violations, (
        f"api/domain이 DB를 import합니다:\n" + "\n".join(violations)
    )
