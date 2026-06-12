from datetime import datetime, timedelta, timezone

from sensors.cert_expiry import days_left, judge


def test_days_left_parses_openssl_enddate():
    assert days_left("notAfter=Jul 22 17:58:41 2026 GMT",
                     now=datetime(2026, 6, 9, tzinfo=timezone.utc)) == 43


def test_expiring_soon_is_krit():
    exp = datetime.now(timezone.utc) + timedelta(days=7)
    f = judge("127.0.0.1:8771", exp)
    assert f is not None and f.severity == "krit"


def test_far_expiry_is_silent():
    exp = datetime.now(timezone.utc) + timedelta(days=200)
    assert judge("127.0.0.1:8771", exp) is None
