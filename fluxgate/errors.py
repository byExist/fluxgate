class CallNotPermittedError(Exception):
    """Raised when a call is not permitted due to circuit breaker state."""
