"""
tests/test_api_rebalancing.py
리밸런싱 알고리즘 유닛 테스트
"""
import pytest
from api.features.targets.schemas import TargetItem
from api.features.rebalancing.repository import get_rebalancing_suggestions


# ── 픽스처 ──────────────────────────────────────────────────────────

def make_target(asset_class: str, current: float, target: float,
                warning_thr: float = 5.0, danger_thr: float = 10.0) -> TargetItem:
    dev = round(current - target, 2)
    if abs(dev) >= danger_thr:
        level = "danger"
    elif abs(dev) >= warning_thr:
        level = "warning"
    else:
        level = "normal"
    return TargetItem(
        asset_class=asset_class,
        currentRatio=current,
        targetRatio=target,
        deviation=dev,
        level=level,
    )


# ── 리밸런싱 제안 테스트 ─────────────────────────────────────────────

class TestRebalancingSuggestions:
    def test_normal_returns_gwanmang(self):
        """괴리가 임계값 이하면 관망 제안"""
        t = make_target("국내주식", current=30.0, target=30.0)
        suggestions = get_rebalancing_suggestions([t])
        assert len(suggestions) == 1
        assert suggestions[0].action == "관망"

    def test_excess_returns_reduction(self):
        """목표 초과 → 비중 축소"""
        t = make_target("해외주식", current=40.0, target=30.0)
        suggestions = get_rebalancing_suggestions([t])
        assert suggestions[0].action == "비중 축소"

    def test_deficit_returns_increase(self):
        """목표 미달 → 비중 확대"""
        t = make_target("채권", current=5.0, target=15.0)
        suggestions = get_rebalancing_suggestions([t])
        assert suggestions[0].action == "비중 확대"

    def test_deviation_preserved_in_suggestion(self):
        """편차 값이 제안에 정확히 포함되는지 확인"""
        t = make_target("현금", current=8.0, target=12.0)
        suggestions = get_rebalancing_suggestions([t])
        assert suggestions[0].deviation == pytest.approx(-4.0, abs=0.01)

    def test_multiple_assets_all_processed(self):
        """여러 자산 모두 처리"""
        targets = [
            make_target("국내주식", 30.0, 30.0),
            make_target("해외주식", 40.0, 30.0),
            make_target("채권", 5.0, 15.0),
        ]
        suggestions = get_rebalancing_suggestions(targets)
        assert len(suggestions) == 3
        actions = {s.asset: s.action for s in suggestions}
        assert actions["국내주식"] == "관망"
        assert actions["해외주식"] == "비중 축소"
        assert actions["채권"] == "비중 확대"

    def test_empty_targets(self):
        """빈 목표 리스트 처리"""
        assert get_rebalancing_suggestions([]) == []

    def test_boundary_at_threshold(self):
        """경계값(임계값 정확히 일치)은 warning으로 처리"""
        # deviation == warning_thr → warning level → 비중 축소
        t = make_target("ETF", current=35.0, target=30.0, warning_thr=5.0)
        assert t.level == "warning"
        suggestions = get_rebalancing_suggestions([t])
        assert suggestions[0].action == "비중 축소"

    def test_danger_level_still_suggests_action(self):
        """danger 레벨도 액션 제안"""
        t = make_target("현금", current=0.0, target=15.0, warning_thr=5.0, danger_thr=10.0)
        assert t.level == "danger"
        suggestions = get_rebalancing_suggestions([t])
        assert suggestions[0].action == "비중 확대"


# ── 편차 계산 정확도 테스트 ─────────────────────────────────────────

class TestDeviationCalculation:
    @pytest.mark.parametrize("current,target,expected_dev", [
        (60.0, 60.0, 0.0),
        (65.0, 60.0, 5.0),
        (55.0, 60.0, -5.0),
        (100.0, 0.0, 100.0),
    ])
    def test_deviation_values(self, current, target, expected_dev):
        t = make_target("테스트자산", current, target)
        assert t.deviation == pytest.approx(expected_dev, abs=0.01)

    @pytest.mark.parametrize("current,target,warning_thr,danger_thr,expected_level", [
        (30.0, 30.0, 3.0, 5.0, "normal"),
        (32.9, 30.0, 3.0, 5.0, "normal"),   # 2.9 < warning_thr(3.0) → normal
        (33.0, 30.0, 3.0, 5.0, "warning"),  # 3.0 >= warning_thr → warning
        (35.0, 30.0, 3.0, 5.0, "danger"),   # 5.0 >= danger_thr → danger
        (24.9, 30.0, 3.0, 5.0, "danger"),   # -5.1 → danger
    ])
    def test_level_assignment(self, current, target, warning_thr, danger_thr, expected_level):
        t = make_target("테스트자산", current, target, warning_thr, danger_thr)
        assert t.level == expected_level
