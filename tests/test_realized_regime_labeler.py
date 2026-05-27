from api.backtest_judgment.realized_regime_labeler import RealizedRegimeLabeler


def test_realized_regime_labeler_labels_future_windows():
    labeler = RealizedRegimeLabeler()
    assert labeler.label([100, 70, 68, 69, 70]).label == "CRASH"
    assert labeler.label([100, 85, 80, 95, 110]).label == "RECOVERY"
    assert labeler.label([100, 101, 100, 101, 100]).label == "BENIGN"
    assert labeler.label([100, 101]).label == "UNKNOWN"
