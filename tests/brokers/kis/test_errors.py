from api.brokers.kis.errors import KISAPIError, KISConfigError, KISNetworkError


def test_kis_errors_are_importable():
    assert issubclass(KISConfigError, RuntimeError)
    assert issubclass(KISAPIError, RuntimeError)
    assert issubclass(KISNetworkError, RuntimeError)


def test_kis_errors_carry_message():
    err = KISConfigError("missing key")
    assert str(err) == "missing key"

    err = KISAPIError("bad response")
    assert str(err) == "bad response"

    err = KISNetworkError("timeout")
    assert str(err) == "timeout"
