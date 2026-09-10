class IHMError(Exception):
    """Expected user-facing error with optional remediation."""

    def __init__(self, message: str, remediation: str | None = None) -> None:
        super().__init__(message)
        self.remediation = remediation
