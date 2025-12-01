"""Tests for retry strategies (Always, Never, Cooldown, Backoff)."""

import time

import pytest

from fluxgate.retries import Always, Never, Cooldown, Backoff


def test_cooldown_invalid_parameters():
    """Cooldown rejects invalid parameters."""
    with pytest.raises(ValueError, match="Duration must be greater than zero"):
        Cooldown(duration=0.0)

    with pytest.raises(ValueError, match="Jitter ratio must be between 0.0 and 1.0"):
        Cooldown(duration=5.0, jitter_ratio=-0.1)

    with pytest.raises(ValueError, match="Jitter ratio must be between 0.0 and 1.0"):
        Cooldown(duration=5.0, jitter_ratio=1.5)


def test_backoff_invalid_parameters():
    """Backoff rejects invalid parameters."""
    with pytest.raises(ValueError, match="Initial duration must be greater than zero"):
        Backoff(initial=0.0, multiplier=2.0)

    with pytest.raises(ValueError, match="Multiplier must be greater than 1.0"):
        Backoff(initial=10.0, multiplier=1.0)

    with pytest.raises(ValueError, match="Max duration must be >= initial duration"):
        Backoff(initial=100.0, multiplier=2.0, max_duration=50.0)

    with pytest.raises(ValueError, match="Jitter ratio must be between 0.0 and 1.0"):
        Backoff(initial=10.0, multiplier=2.0, jitter_ratio=1.5)


def test_always_and_never():
    """Always permits immediately, Never never permits."""
    changed_at = time.time()
    reopens = 0

    # Always permits
    retry = Always()
    assert retry(changed_at, reopens) is True
    assert retry(changed_at - 100, reopens) is True

    # Never permits
    retry = Never()
    assert retry(changed_at, reopens) is False
    assert retry(changed_at - 100, reopens) is False


def test_cooldown_waits_for_duration():
    """Cooldown denies before duration, permits after."""
    retry = Cooldown(duration=5.0)
    reopens = 0

    # Just changed - should deny
    changed_at = time.time()
    assert retry(changed_at, reopens) is False

    # 3 seconds ago - still deny
    changed_at = time.time() - 3.0
    assert retry(changed_at, reopens) is False

    # 5+ seconds ago - permit
    changed_at = time.time() - 5.1
    assert retry(changed_at, reopens) is True


def test_cooldown_with_jitter():
    """Cooldown with jitter varies actual wait time."""
    retry = Cooldown(duration=5.0, jitter_ratio=0.2)
    reopens = 0

    # Test many times - should not always return same result at boundary
    # Due to jitter, ±20% means 4.0s to 6.0s actual duration
    changed_at = time.time() - 5.0

    # Run 100 times and check that results vary (some true, some false)
    results = [retry(changed_at, reopens) for _ in range(100)]
    # Not all should be the same due to jitter
    assert not all(results) and any(results)


def test_backoff_exponential_increase():
    """Backoff increases wait time exponentially with reopens count."""
    retry = Backoff(initial=2.0, multiplier=2.0, max_duration=100.0)

    # reopens=0: 2s
    changed_at = time.time() - 2.1
    assert retry(changed_at, reopens=0) is True

    changed_at = time.time() - 1.9
    assert retry(changed_at, reopens=0) is False

    # reopens=1: 4s (2 * 2^1)
    changed_at = time.time() - 4.1
    assert retry(changed_at, reopens=1) is True

    changed_at = time.time() - 3.9
    assert retry(changed_at, reopens=1) is False

    # reopens=2: 8s (2 * 2^2)
    changed_at = time.time() - 8.1
    assert retry(changed_at, reopens=2) is True

    changed_at = time.time() - 7.9
    assert retry(changed_at, reopens=2) is False


def test_backoff_respects_max_duration():
    """Backoff caps wait time at max_duration."""
    retry = Backoff(initial=10.0, multiplier=2.0, max_duration=30.0)

    # reopens=0: 10s
    changed_at = time.time() - 10.1
    assert retry(changed_at, reopens=0) is True

    # reopens=1: 20s
    changed_at = time.time() - 20.1
    assert retry(changed_at, reopens=1) is True

    # reopens=2: would be 40s, but capped at 30s
    changed_at = time.time() - 30.1
    assert retry(changed_at, reopens=2) is True

    changed_at = time.time() - 29.9
    assert retry(changed_at, reopens=2) is False

    # reopens=10: still capped at 30s
    changed_at = time.time() - 30.1
    assert retry(changed_at, reopens=10) is True


def test_backoff_with_jitter():
    """Backoff with jitter varies actual wait time."""
    retry = Backoff(initial=5.0, multiplier=2.0, jitter_ratio=0.2)
    reopens = 0

    # At boundary (5.0s with ±20% jitter = 4.0s to 6.0s)
    changed_at = time.time() - 5.0

    # Run many times - results should vary due to jitter
    results = [retry(changed_at, reopens) for _ in range(100)]
    assert not all(results) and any(results)
