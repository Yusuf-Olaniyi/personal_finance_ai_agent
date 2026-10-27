from finance_coach.guard import UsageGuard


def test_busy_then_cooldown_then_allowed_again():
    now = [1000.0]
    g = UsageGuard(daily_cap=10, cooldown_s=30, clock=lambda: now[0])
    assert g.try_start()[0]
    ok, msg = g.try_start()
    assert not ok and "running" in msg
    g.finish()
    ok, msg = g.try_start()
    assert not ok and "cooling" in msg
    now[0] += 31
    assert g.try_start()[0]


def test_daily_cap():
    g = UsageGuard(daily_cap=2, cooldown_s=0)
    for _ in range(2):
        assert g.try_start()[0]
        g.finish()
    ok, msg = g.try_start()
    assert not ok and "daily" in msg