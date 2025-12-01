class CallNotPermittedError(Exception):
    """Raised when a call is not permitted due to circuit breaker state."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
