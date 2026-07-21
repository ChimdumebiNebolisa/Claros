from rate_limit import SlidingWindowRateLimiter


def test_sliding_window_rate_limiter_blocks_then_recovers():
    limiter = SlidingWindowRateLimiter(window_seconds=10)
    assert limiter.allow("upload:client", 2, now=0)
    assert limiter.allow("upload:client", 2, now=1)
    assert not limiter.allow("upload:client", 2, now=2)
    assert limiter.allow("upload:client", 2, now=11)
