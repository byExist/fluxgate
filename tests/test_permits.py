"""Tests for permit strategies (Random, RampUp)."""

import time

import pytest

from fluxgate.permits import Random, RampUp


def test_random_probabilistic_behavior():
    """Random permit allows calls based on probability ratio."""
    # Test with 50% probability - run many times and check distribution
    permit = Random(ratio=0.5)
    changed_at = time.time()

    # Run 1000 times and check approximate 50% pass rate
    passes = sum(permit(changed_at) for _ in range(1000))
    # Allow 5% margin of error (450-550 passes out of 1000)
    assert 450 <= passes <= 550


def test_random_boundary_values():
    """Random permit handles boundary ratios correctly."""
    changed_at = time.time()

    # ratio=0.0 - never permits
    permit = Random(ratio=0.0)
    for _ in range(100):
        assert permit(changed_at) is False

    # ratio=1.0 - always permits
    permit = Random(ratio=1.0)
    for _ in range(100):
        assert permit(changed_at) is True


def test_random_invalid_ratio():
    """Random rejects invalid ratio values."""
    with pytest.raises(ValueError, match="Ratio must be between 0.0 and 1.0"):
        Random(ratio=-0.1)

    with pytest.raises(ValueError, match="Ratio must be between 0.0 and 1.0"):
        Random(ratio=1.5)


def test_rampup_initial_phase():
    """RampUp starts with initial ratio."""
    permit = RampUp(initial=0.1, final=0.8, duration=10.0)
    changed_at = time.time()

    # Immediately after state change, should use initial ratio (10%)
    passes = sum(permit(changed_at) for _ in range(1000))
    # Allow margin: 50-150 passes (10% ± 5%)
    assert 50 <= passes <= 150


def test_rampup_progression():
    """RampUp gradually increases ratio over time."""
    permit = RampUp(initial=0.0, final=1.0, duration=10.0)

    # Simulate time progression
    changed_at = time.time() - 5.0  # 5 seconds ago

    # After 5 seconds (50% of duration), ratio should be ~0.5
    passes = sum(permit(changed_at) for _ in range(1000))
    # Allow margin: 400-600 passes (50% ± 10%)
    assert 400 <= passes <= 600


def test_rampup_completion():
    """RampUp uses final ratio after duration expires."""
    permit = RampUp(initial=0.1, final=0.9, duration=10.0)

    # Simulate 10+ seconds elapsed
    changed_at = time.time() - 15.0

    # After duration, should use final ratio (90%)
    passes = sum(permit(changed_at) for _ in range(1000))
    # Allow margin: 850-950 passes (90% ± 5%)
    assert 850 <= passes <= 950


def test_rampup_invalid_parameters():
    """RampUp rejects invalid parameter combinations."""
    with pytest.raises(
        ValueError, match="Initial and final must be between 0.0 and 1.0"
    ):
        RampUp(initial=-0.1, final=0.8, duration=10.0)

    with pytest.raises(
        ValueError, match="Initial and final must be between 0.0 and 1.0"
    ):
        RampUp(initial=0.1, final=1.5, duration=10.0)

    with pytest.raises(ValueError, match="Duration must be greater than zero"):
        RampUp(initial=0.1, final=0.8, duration=0.0)
