from sensors.disk_trend import hours_to_full


def test_growing_disk_extrapolates():
    # 1 GiB/h Wachstum, 8 GiB frei am Ende -> ~8h
    samples = [
        {"ts": 0,     "used": 100 * 2**30, "size": 110 * 2**30},
        {"ts": 3600,  "used": 101 * 2**30, "size": 110 * 2**30},
        {"ts": 7200,  "used": 102 * 2**30, "size": 110 * 2**30},
    ]
    h = hours_to_full(samples)
    assert h is not None and 7.5 < h < 8.5  # 8 GiB frei / 1 GiB/h


def test_shrinking_disk_returns_none():
    samples = [
        {"ts": 0,    "used": 100, "size": 200},
        {"ts": 3600, "used": 90,  "size": 200},
        {"ts": 7200, "used": 80,  "size": 200},
    ]
    assert hours_to_full(samples) is None


def test_too_few_samples_returns_none():
    assert hours_to_full([{"ts": 0, "used": 1, "size": 2}]) is None
