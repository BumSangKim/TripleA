from __future__ import annotations

from datetime import date

from api.domain.strategy_inputs import StrategyDecisionLogInput
from api.strategy.data_ports import StrategyDecisionLogWriter


def log_strategy_decision(
    writer: StrategyDecisionLogWriter | None,
    *,
    enabled: bool,
    decision_id: str,
    as_of_date: date,
    decision_type: str,
    payload: dict,
    snapshot_id: str | None = None,
    reason_codes: list[str] | None = None,
    warnings: list[str] | None = None,
) -> bool:
    if not enabled or writer is None:
        return False
    log_payload = StrategyDecisionLogInput(
        decision_id=decision_id,
        snapshot_id=snapshot_id,
        as_of_date=as_of_date,
        decision_type=decision_type,
        payload=payload,
        reason_codes=reason_codes or [],
        warnings=warnings or [],
    )
    return writer.write_decision_log(log_payload, enabled=True)
