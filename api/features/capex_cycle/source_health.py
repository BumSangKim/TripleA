from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from api.data.capex_models import DataQualityIssueRecord, SourceFetchLogRecord
from api.features.capex_cycle.report_schemas import SourceHealthItem
from api.features.capex_cycle.schemas import ReasonItem, WarningItem


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_CATALOG_PATH = PROJECT_ROOT / "config" / "data_sources" / "capex_cycle_sources.yaml"


class CapexSourceHealthStatus(StrEnum):
    OK = "OK"
    STALE = "STALE"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    DISABLED = "DISABLED"
    FIXTURE_ONLY = "FIXTURE_ONLY"


@dataclass(frozen=True)
class SourceHealthPolicy:
    source_group: str
    provider: str
    enabled_by_default: bool
    optional: bool
    stale_after_days: int


def compute_capex_source_health(
    repository: Any,
    *,
    as_of_date: date,
    source_catalog_path: Path = SOURCE_CATALOG_PATH,
) -> list[SourceHealthItem]:
    policies = _source_policies(source_catalog_path)
    logs = tuple(repository.list_fetch_logs(limit=1000))
    issues = tuple(repository.list_quality_issues(limit=1000))
    items: list[SourceHealthItem] = []
    matched_log_ids: set[str] = set()
    for policy in policies:
        source_logs = _matching_logs(logs, policy)
        matched_log_ids.update(log.fetch_id for log in source_logs)
        source_issues = _matching_issues(issues, policy)
        items.append(_health_item(policy, source_logs, source_issues, as_of_date=as_of_date))

    for log in logs:
        if log.fetch_id in matched_log_ids or not _is_fixture_source(log.source_id):
            continue
        items.append(
            SourceHealthItem(
                source_id=log.source_id,
                status=CapexSourceHealthStatus.FIXTURE_ONLY.value,
                quality_score=0.5,
                last_available_at=log.finished_at or log.started_at,
                warnings=[_poor_health_warning(log.source_id, CapexSourceHealthStatus.FIXTURE_ONLY)],
                reason_codes=[ReasonItem(code="SOURCE_HEALTH_FIXTURE_ONLY", category="data_health", detail=log.source_id)],
            )
        )
    return items


def _health_item(
    policy: SourceHealthPolicy,
    logs: Sequence[SourceFetchLogRecord],
    issues: Sequence[DataQualityIssueRecord],
    *,
    as_of_date: date,
) -> SourceHealthItem:
    if policy.optional and not policy.enabled_by_default:
        status = CapexSourceHealthStatus.DISABLED
        return SourceHealthItem(
            source_id=policy.provider,
            status=status.value,
            quality_score=0.0,
            last_available_at=None,
            warnings=[_poor_health_warning(policy.provider, status)],
            reason_codes=[ReasonItem(code="SOURCE_HEALTH_DISABLED", category="data_health", detail=policy.source_group)],
        )
    if not logs:
        status = CapexSourceHealthStatus.MISSING
        return SourceHealthItem(
            source_id=policy.provider,
            status=status.value,
            quality_score=0.0,
            last_available_at=None,
            warnings=[_poor_health_warning(policy.provider, status)],
            reason_codes=[ReasonItem(code="SOURCE_HEALTH_MISSING", category="data_health", detail=policy.source_group)],
        )

    latest = max(logs, key=lambda log: log.finished_at or log.started_at)
    last_available_at = latest.finished_at or latest.started_at
    issue_severity = {issue.severity for issue in issues}
    if _is_fixture_source(latest.source_id):
        status = CapexSourceHealthStatus.FIXTURE_ONLY
    elif latest.status == "PARTIAL_SUCCESS" or issue_severity & {"ERROR", "BLOCKER"}:
        status = CapexSourceHealthStatus.PARTIAL
    elif latest.status in {"FAILED", "SKIPPED"}:
        status = CapexSourceHealthStatus.MISSING
    elif (as_of_date - last_available_at.date()).days > policy.stale_after_days:
        status = CapexSourceHealthStatus.STALE
    else:
        status = CapexSourceHealthStatus.OK

    warnings = [_poor_health_warning(policy.provider, status)] if status is not CapexSourceHealthStatus.OK else []
    warnings.extend(
        WarningItem(
            code=f"SOURCE_HEALTH_ISSUE_{issue.severity}",
            severity="WARNING" if issue.severity in {"INFO", "WARNING"} else "ERROR",
            source="source_health",
            message=f"{issue.metric_id}: {issue.reason_code}",
        )
        for issue in issues
    )
    return SourceHealthItem(
        source_id=policy.provider,
        status=status.value,
        quality_score=_quality_score(status, issues),
        last_available_at=last_available_at,
        warnings=warnings,
        reason_codes=[ReasonItem(code=f"SOURCE_HEALTH_{status.value}", category="data_health", detail=policy.source_group)],
    )


def _source_policies(path: Path) -> tuple[SourceHealthPolicy, ...]:
    data = yaml.safe_load(path.read_text()) if path.exists() else {}
    groups = data.get("source_groups") or {}
    metrics = data.get("metrics") or {}
    policies: list[SourceHealthPolicy] = []
    for source_group, config in groups.items():
        stale_values = [
            int(metric.get("stale_after_days", 30))
            for metric in metrics.values()
            for source in metric.get("source_priority", [])
            if source.get("source_group") == source_group
        ]
        policies.append(
            SourceHealthPolicy(
                source_group=str(source_group),
                provider=str(config.get("provider") or source_group),
                enabled_by_default=bool(config.get("enabled_by_default")),
                optional=bool(config.get("optional")),
                stale_after_days=min(stale_values) if stale_values else 30,
            )
        )
    return tuple(policies)


def _matching_logs(logs: Sequence[SourceFetchLogRecord], policy: SourceHealthPolicy) -> tuple[SourceFetchLogRecord, ...]:
    names = {_norm(policy.source_group), _norm(policy.provider)}
    return tuple(log for log in logs if _norm(log.source_id) in names)


def _matching_issues(issues: Sequence[DataQualityIssueRecord], policy: SourceHealthPolicy) -> tuple[DataQualityIssueRecord, ...]:
    names = {_norm(policy.source_group), _norm(policy.provider)}
    return tuple(issue for issue in issues if _norm(issue.source_id) in names)


def _poor_health_warning(source_id: str, status: CapexSourceHealthStatus) -> WarningItem:
    return WarningItem(
        code="SOURCE_HEALTH_RISK_INCREASE_BLOCKED",
        severity="WARNING",
        source="source_health",
        message=f"{source_id} status={status.value}; REVIEW_REQUIRED before risk increase",
    )


def _quality_score(status: CapexSourceHealthStatus, issues: Sequence[DataQualityIssueRecord]) -> float:
    base = {
        CapexSourceHealthStatus.OK: 1.0,
        CapexSourceHealthStatus.STALE: 0.5,
        CapexSourceHealthStatus.PARTIAL: 0.5,
        CapexSourceHealthStatus.MISSING: 0.0,
        CapexSourceHealthStatus.DISABLED: 0.0,
        CapexSourceHealthStatus.FIXTURE_ONLY: 0.5,
    }[status]
    penalty = 0.1 * len([issue for issue in issues if issue.severity in {"ERROR", "BLOCKER"}])
    return max(0.0, round(base - penalty, 4))


def _is_fixture_source(source_id: str) -> bool:
    return "fixture" in source_id.lower()


def _norm(value: str) -> str:
    return value.lower().replace("_", "")
