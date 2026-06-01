from __future__ import annotations

from api.features.backtests.sector_component_data_provider import FileSectorComponentBacktestDataProvider


def test_file_sector_component_data_provider_reads_local_inputs(tmp_path) -> None:
    path = tmp_path / "inputs.yaml"
    path.write_text(
        """
observations:
  - sector_id: SEMICONDUCTOR
    component_name: trade
historical_returns:
  - sector_id: SEMICONDUCTOR
    forward_return: 0.01
macro_regime_records:
  - sector_id: SEMICONDUCTOR
    regime: risk_on
""",
        encoding="utf-8",
    )
    provider = FileSectorComponentBacktestDataProvider(path)

    assert provider.list_sector_component_observations(None)[0]["component_name"] == "trade"
    assert provider.list_sector_component_returns(None)[0]["forward_return"] == 0.01
    assert provider.list_sector_component_regimes(None)[0]["regime"] == "risk_on"


def test_missing_file_returns_empty_read_only_inputs(tmp_path) -> None:
    provider = FileSectorComponentBacktestDataProvider(tmp_path / "missing.yaml")

    assert provider.list_sector_component_observations(None) == ()
    assert provider.list_sector_component_returns(None) == ()
    assert provider.list_sector_component_regimes(None) == ()
