from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from api.strategy.ai_capex_token_component import AICapexTokenDiagnosticComponent
from api.strategy.ai_capex_token_input_adapter import AICapexTokenInputAdapter


PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "ai_capex_token"
CONFIG_PATH = PROJECT_ROOT / "config" / "scoring" / "ai_capex_token.yaml"
FIXTURES = (
    "s1_expanding_accelerating.json",
    "s3_expanding_decelerating_platform.json",
    "s7_contracting_accelerating_overinvestment.json",
    "future_data_leakage_probe.json",
)
TEST_CONFIG = {
    "enabled": False,
    "diagnostic_only": True,
    "normalization_parameters": {"metadata": {"approved": True}},
    "scenario_probability_parameters": {"membership_strength": 0.8},
}


def build_ai_capex_token_backtest_diagnostic() -> dict[str, Any]:
    config = _load_config()
    rows: list[dict[str, Any]] = []
    reason_codes: list[str] = ["AI_CAPEX_TOKEN_DIAGNOSTIC_ONLY"]
    warnings: list[dict[str, Any]] = []

    for fixture_name in FIXTURES:
        payload = _load_fixture(fixture_name)
        adapter_result = AICapexTokenInputAdapter().adapt_with_metadata(payload)
        if adapter_result.snapshot is None:
            rows.append(
                {
                    "fixtureId": fixture_name.removesuffix(".json"),
                    "snapshotId": payload.get("snapshot_id", fixture_name),
                    "intendedScenario": payload.get("metadata", {}).get("intended_scenario"),
                    "dominantScenario": None,
                    "status": adapter_result.fallback_state or "REVIEW_REQUIRED",
                    "componentCount": 0,
                    "maxConfidence": 0.0,
                    "minDataQuality": 0.0,
                    "reasonCodes": list(adapter_result.reason_codes),
                    "excludedMetricKeys": list(adapter_result.excluded_metric_keys),
                }
            )
            reason_codes.extend(adapter_result.reason_codes)
            warnings.append(
                {
                    "code": "AI_CAPEX_TOKEN_FIXTURE_REVIEW_REQUIRED",
                    "message": f"{fixture_name} requires review before diagnostic scoring",
                    "fallbackState": adapter_result.fallback_state or "REVIEW_REQUIRED",
                }
            )
            continue

        diagnostic = AICapexTokenDiagnosticComponent().build(payload, config=TEST_CONFIG)
        component_payloads = [asdict(component) for component in diagnostic.components]
        row_reason_codes = _unique(
            [
                *diagnostic.reason_codes,
                *(code for component in diagnostic.components for code in component.reason_codes),
            ]
        )
        rows.append(
            {
                "fixtureId": fixture_name.removesuffix(".json"),
                "snapshotId": payload.get("snapshot_id", fixture_name),
                "intendedScenario": payload.get("metadata", {}).get("intended_scenario"),
                "dominantScenario": diagnostic.components[0].scenario_distribution.dominant_scenario
                if diagnostic.components
                else None,
                "status": "DIAGNOSTIC_ONLY",
                "componentCount": len(diagnostic.components),
                "maxConfidence": max((component.confidence for component in diagnostic.components), default=0.0),
                "minDataQuality": min((component.data_quality for component in diagnostic.components), default=0.0),
                "reasonCodes": row_reason_codes,
                "excludedMetricKeys": list(adapter_result.excluded_metric_keys),
                "components": component_payloads,
            }
        )
        reason_codes.extend(row_reason_codes)

    return {
        "ok": True,
        "status": "DIAGNOSTIC_ONLY",
        "diagnosticOnly": True,
        "productionReady": False,
        "parameterVersion": _config_value(config, ("parameter_metadata", "parameter_version"), "ai_capex_token_v0_draft"),
        "modelVersion": _config_value(config, ("parameter_metadata", "model_version"), "ai_capex_token_score_v0"),
        "dataSnapshotId": "ai-capex-token-backtest-ui-diagnostic:v1",
        "productionGate": {
            "enabled": bool(config.get("enabled")),
            "productionEnabled": bool(config.get("production_enabled")),
            "approved": bool(_config_value(config, ("parameter_metadata", "approved"), False)),
            "requiresBacktestPass": bool(config.get("requires_backtest_pass")),
            "requiresWalkForwardPass": bool(config.get("requires_walk_forward_pass")),
        },
        "scenarioRows": rows,
        "reasonCodes": _unique(reason_codes),
        "warnings": warnings,
    }


def _load_config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _config_value(config: dict[str, Any], path: tuple[str, ...], default: Any) -> Any:
    value: Any = config
    for key in path:
        if not isinstance(value, dict):
            return default
        value = value.get(key)
    return default if value is None else value


def _unique(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
