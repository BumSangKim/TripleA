# Current Structure Inventory

생성일: 2026-05-28  
목적: 리팩토링 전 현재 파일 구조, 주요 import 경로, 테스트 구조, legacy 파일 사용처 조사

---

## 1. api/ 최상위 파일 (flat 모듈)

legacy 파일 (shim 금지 대상):
- `api/db.py` — DB 연결, migrate/ensure 함수들
- `api/kis.py` — KIS API 클라이언트
- `api/modes.py` — TradingMode enum/policy
- `api/providers.py` — 데이터 provider 추상화
- `api/services.py` — 잡다한 서비스 함수 모음
- `api/models.py` — 공통 모델
- `api/strategy_config.py` — 전략 설정
- `api/data_contracts.py` — 데이터 계약 모델
- `api/observation_universe.py`
- `api/backtest_engine.py`, `api/backtest_foundation.py`
- `api/macro_data_service.py`, `api/macro_indicator_collector.py`, `api/macro_telegram_report.py`
- `api/market_data_collector.py`, `api/market_data_service.py`
- `api/trade_data_service.py`, `api/bottleneck_data_service.py`
- `api/telegram_service.py`
- `api/asset_universe_*.py` (loader, mapping, schema, snapshot, validator)
- `api/main.py`

## 2. api/ 서브패키지

| 패키지 | 설명 |
|--------|------|
| `api/data/` | ingestion, repository, quality, providers, snapshot |
| `api/intraday/` | 장중 모니터링 (alert, collector, detector, models, provider, repository, router, universe, config) |
| `api/market_data/` | models, price_provider, repository |
| `api/strategy/` | 투자 판단 로직 (allocator, score, macro, sector 등) |
| `api/score_pipeline/` | 점수 파이프라인 (audit, backtest, contracts, engines, features, scoring, parameters) |
| `api/plugin_boundary/` | 플러그인 계약/레지스트리 |
| `api/optimization/` | 파라미터 최적화 |
| `api/universe/` | 자산 universe 관리 (loader, selector, snapshot, validator) |
| `api/backtest_judgment/` | 백테스트 평가 (evaluator, realized_regime_labeler) |
| `api/testbed/` | 테스트베드 (schema, snapshot_service) |

## 3. Legacy Import 현황 (grep 결과)

### api/db import 사용처
```
api/intraday/router.py           from api.db import get_conn
tests/test_api_accounts.py       from api.db import _migrate_dashboard_tables
tests/test_backtest_engine.py    from api.db import ensure_dashboard_tables
tests/test_bottleneck_sector_engine.py  from api.db import ensure_dashboard_tables
tests/test_intraday_api.py       import api.db as api_db
tests/test_intraday_strategy_isolation.py  from api.db import ensure_dashboard_tables / import api.db as api_db
tests/test_market_data_schema.py from api.db import ensure_dashboard_tables
tests/test_market_data_service.py from api.db import ensure_dashboard_tables
tests/test_modes.py              from api.db import ensure_dashboard_tables
tests/test_trade_bottleneck_data_services.py  from api.db import ensure_dashboard_tables
tests/test_triplea_allocator.py  from api.db import ensure_dashboard_tables
```

### api/modes import 사용처
```
tests/test_api_engine.py         from api.modes import TradingMode
tests/test_modes.py              from api.modes import TradingMode, get_mode_policy, normalize_mode
```

### api/kis import 사용처
```
api/market_data/price_provider.py  from api.kis import DEMO_BASE_URL, PROJECT_ROOT, REAL_BASE_URL, _bool_env, _clean, to_decimal
tests/test_api_endpoints.py        from api.kis import KISConfigError
tests/test_kis_provider.py         from api.kis import (...)
```

### api/intraday 내부 import (정상 — shim 대상 아님)
```
api/intraday/__init__.py, alert.py, collector.py, detector.py, provider.py, repository.py, router.py, universe.py
→ 모두 api.intraday.* 내부 참조 (정상)
```

## 4. 테스트 디렉터리 구조

```
tests/
├── conftest.py
├── test_api_accounts.py
├── test_api_backtests.py
├── test_api_endpoints.py
├── test_api_engine.py
├── test_api_market_data.py
├── test_api_orders.py
├── test_api_rebalancing.py
├── test_api_strategy_metadata.py
├── test_asset_*.py (6개)
├── test_backtest_*.py (3개)
├── test_bottleneck_*.py (2개)
├── test_candidate_generator.py
├── test_config_metadata.py
├── test_current_quote_connectivity.py
├── test_data_*.py (8개)
├── test_decision_logging_integration.py
├── test_failure_analyzer.py
├── test_indicator_plugin_registry.py
├── test_intraday_*.py (7개)
├── test_judgment_backtest_evaluator.py
├── test_kis_provider.py
├── test_macro_*.py (5개)
├── test_market_data_*.py (5개)
├── test_modes.py
├── test_optimization_*.py
├── test_score_pipeline_*.py
├── test_strategy_*.py
└── ... (100+ test files)
```

## 5. 테스트 실행 방법

```bash
pytest               # 전체 테스트
pytest tests/        # tests 디렉터리 명시
pytest -q            # 간결 출력
```

## 6. 요약

- **legacy shim 금지 대상**: `api/db.py`, `api/modes.py`, `api/kis.py`, `api/providers.py`
- **현재 legacy import 건수**: db=11곳, modes=2곳, kis=3곳
- **신규 서브패키지**: `api/domain/`, `api/core/`는 아직 없음 (이번 리팩토링에서 생성 예정)
- **features 수직 슬라이스**: `api/features/`는 아직 없음
