from typing import Optional

class AirportSearchException(Exception):
    """Base exception for all application errors."""
    def __init__(self, message: str, code: str, field: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.field = field

class InvalidQueryException(AirportSearchException):
    """Raised when search query fails validation."""
    def __init__(self, message: str, field: str = "q"):
        super().__init__(message, code="INVALID_QUERY", field=field)

class DataLoadException(AirportSearchException):
    """Raised when application data files cannot be loaded."""
    def __init__(self, message: str):
        super().__init__(message, code="DATA_LOAD_ERROR")

class LimitValidationException(AirportSearchException):
    """Raised when limit bounds are exceeded."""
    def __init__(self, message: str, field: str = "limit"):
        super().__init__(message, code="INVALID_LIMIT", field=field)
