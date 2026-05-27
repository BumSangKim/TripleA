import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _python_files(paths: list[Path]) -> list[Path]:
    files = []
    for path in paths:
        if path.is_dir():
            files.extend(path.rglob("*.py"))
        elif path.exists():
            files.append(path)
    return sorted(files)


def test_strategy_code_does_not_hardcode_asset_symbols():
    strategy_paths = [
        REPO_ROOT / "api" / "strategy",
        REPO_ROOT / "api" / "allocation",
        REPO_ROOT / "api" / "risk",
    ]
    files = _python_files(strategy_paths)
    ticker_pattern = re.compile(r"\b(?:\d{6}|SPY|QQQ|NVDA|MSFT|005930|000660)\b")

    offenders = []
    for path in files:
        matches = ticker_pattern.findall(path.read_text(encoding="utf-8"))
        if matches:
            offenders.append(f"{path.relative_to(REPO_ROOT)}: {sorted(set(matches))}")

    assert not offenders, "\n".join(offenders)


def test_new_universe_and_market_data_code_has_no_execution_surface():
    code_paths = _python_files([
        REPO_ROOT / "api" / "universe",
        REPO_ROOT / "api" / "market_data",
    ])
    dangerous_patterns = [
        r"\bplace_order\b",
        r"\bsubmit_order\b",
        r"\bsend_order\b",
        r"\bcreate_order\b",
        r"\bbuy\s*\(",
        r"\bsell\s*\(",
        r"\bavailable_cash\b",
        r"\bpassword\b",
        "주문",
        "매수",
        "매도",
        "잔고",
        "매수가능",
        "계좌비밀번호",
    ]

    offenders = []
    for path in code_paths:
        text = path.read_text(encoding="utf-8")
        for pattern in dangerous_patterns:
            if re.search(pattern, text):
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {pattern}")

    assert not offenders, "\n".join(offenders)
