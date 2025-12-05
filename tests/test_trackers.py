"""Tests for exception trackers (All, TypeOf, Custom, and logical operators)."""

import pytest

from fluxgate.trackers import All, TypeOf, Custom


def test_all_matches_all_exceptions():
    """All tracker matches any exception."""
    tracker = All()
    assert tracker(ValueError("test")) is True
    assert tracker(TypeError("test")) is True
    assert tracker(RuntimeError("test")) is True
    assert tracker(Exception("test")) is True


def test_all_with_negation():
    """All tracker can be combined with negation to exclude specific exceptions."""
    # Track all except ValueError
    tracker = All() & ~TypeOf(ValueError)
    assert tracker(ValueError("test")) is False
    assert tracker(TypeError("test")) is True
    assert tracker(RuntimeError("test")) is True


def test_typeof_empty_types_raises():
    """TypeOf raises ValueError when no types are provided."""
    with pytest.raises(ValueError, match="At least one exception type is required"):
        TypeOf()


def test_typeof_matches_exception_types():
    """TypeOf matches single/multiple types and their subclasses."""
    # Single type
    tracker = TypeOf(ValueError)
    assert tracker(ValueError("test")) is True
    assert tracker(TypeError("test")) is False

    # Multiple types
    tracker = TypeOf(ValueError, TypeError)
    assert tracker(ValueError("test")) is True
    assert tracker(TypeError("test")) is True
    assert tracker(RuntimeError("test")) is False

    # Subclass matching
    tracker = TypeOf(OSError)
    assert tracker(FileNotFoundError("test")) is True  # Subclass of OSError
    assert tracker(PermissionError("test")) is True  # Subclass of OSError
    assert tracker(ValueError("test")) is False


def test_custom_predicate():
    """Custom tracker uses arbitrary predicate function."""

    # Simple predicate
    def has_code_in_message(e: Exception) -> bool:
        return "code" in str(e)

    tracker = Custom(has_code_in_message)
    assert tracker(ValueError("error code 500")) is True
    assert tracker(ValueError("generic error")) is False

    # Attribute-based predicate
    class CustomError(Exception):
        def __init__(self, message: str, code: int):
            super().__init__(message)
            self.code = code

    def is_5xx_error(e: Exception) -> bool:
        return isinstance(e, CustomError) and 500 <= e.code < 600

    tracker = Custom(is_5xx_error)
    assert tracker(CustomError("server error", 503)) is True
    assert tracker(CustomError("client error", 404)) is False
    assert tracker(ValueError("test")) is False


def test_and_operator():
    """AND operator requires both conditions to be true."""
    tracker = TypeOf(ValueError) & Custom(lambda e: "critical" in str(e))

    assert tracker(ValueError("critical error")) is True
    assert tracker(ValueError("minor error")) is False
    assert tracker(TypeError("critical error")) is False


def test_or_operator():
    """OR operator matches if either condition is true."""
    tracker = TypeOf(ValueError) | TypeOf(TypeError)

    assert tracker(ValueError("test")) is True
    assert tracker(TypeError("test")) is True
    assert tracker(RuntimeError("test")) is False


def test_not_operator():
    """NOT operator inverts the condition."""
    tracker = ~TypeOf(ValueError)

    assert tracker(ValueError("test")) is False
    assert tracker(TypeError("test")) is True
    assert tracker(RuntimeError("test")) is True


def test_complex_logical_expressions():
    """Complex combinations of logical operators work correctly."""
    # (ValueError OR TypeError) AND (message contains "critical") AND NOT RuntimeError
    tracker = (
        (TypeOf(ValueError) | TypeOf(TypeError))
        & Custom(lambda e: "critical" in str(e))
        & ~TypeOf(RuntimeError)
    )

    assert tracker(ValueError("critical error")) is True
    assert tracker(TypeError("critical error")) is True
    assert tracker(ValueError("minor error")) is False
    assert tracker(RuntimeError("critical error")) is False

    # NOT (ValueError AND contains "skip")
    tracker = ~(TypeOf(ValueError) & Custom(lambda e: "skip" in str(e)))

    assert tracker(ValueError("skip this")) is False
    assert tracker(ValueError("process this")) is True
    assert tracker(TypeError("skip this")) is True


def test_nested_logical_operators():
    """Logical operators can be nested (AND of AND, OR of OR)."""
    # (A & B) & C - all three must match
    tracker = (TypeOf(ValueError, TypeError) & TypeOf(Exception)) & TypeOf(ValueError)
    assert tracker(ValueError("test")) is True
    assert tracker(TypeError("test")) is False

    # (A | B) | C - any one must match
    tracker = (TypeOf(ValueError) | TypeOf(TypeError)) | TypeOf(KeyError)
    assert tracker(ValueError("test")) is True
    assert tracker(TypeError("test")) is True
    assert tracker(KeyError("test")) is True
    assert tracker(RuntimeError("test")) is False


def test_mixed_logical_operators():
    """Mixed AND/OR operators can be combined."""
    # (A & B) | C - either (A and B) or C
    tracker = (TypeOf(ValueError) & TypeOf(Exception)) | TypeOf(RuntimeError)
    assert tracker(ValueError("test")) is True
    assert tracker(RuntimeError("test")) is True
    assert tracker(KeyError("test")) is False

    # (A | B) & C - (A or B) and C
    tracker = (TypeOf(ValueError) | TypeOf(RuntimeError)) & Custom(
        lambda e: "test" in str(e)
    )
    assert tracker(ValueError("test")) is True
    assert tracker(RuntimeError("test")) is True
    assert tracker(ValueError("other")) is False

    # ~A & B - NOT A and B
    tracker = ~TypeOf(ValueError) & TypeOf(Exception)
    assert tracker(ValueError("test")) is False
    assert tracker(TypeError("test")) is True

    # ~A | B - NOT A or B
    tracker = ~TypeOf(ValueError) | TypeOf(RuntimeError)
    assert tracker(ValueError("test")) is False
    assert tracker(RuntimeError("test")) is True
    assert tracker(TypeError("test")) is True

    # ~(A | B) - NOT (A or B)
    tracker = ~(TypeOf(ValueError) | TypeOf(TypeError))
    assert tracker(ValueError("test")) is False
    assert tracker(TypeError("test")) is False
    assert tracker(RuntimeError("test")) is True

    # ~~A - double negation returns original
    tracker = ~~TypeOf(ValueError)
    assert tracker(ValueError("test")) is True
    assert tracker(TypeError("test")) is False
