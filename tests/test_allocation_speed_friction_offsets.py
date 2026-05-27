from api.strategy.allocation_offsets import apply_speed_and_friction_offsets


def test_speed_and_friction_offsets_are_optional():
    target = {"A": .7, "B": .3}
    previous = {"A": .5, "B": .5}
    unchanged = apply_speed_and_friction_offsets(target, None)
    limited = apply_speed_and_friction_offsets(target, previous, max_change_per_rebalance=.05)
    banded = apply_speed_and_friction_offsets({"A": .51, "B": .49}, previous, rebalance_band=.02)
    urgent = apply_speed_and_friction_offsets(target, previous, max_change_per_rebalance=.05, high_urgency=True)
    assert unchanged == target
    assert limited["A"] < target["A"]
    assert banded == previous
    assert urgent["A"] > limited["A"]
