"""Application-level errors with stable HTTP status and API error codes."""


class AppError(Exception):
    """Base error for failures that can be safely returned through the API."""

    def __init__(self, message: str, status_code: int = 400, error_code: str = "app_error"):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class NotFoundError(AppError):
    """Raised when a requested catalog or application record does not exist."""

    def __init__(self, message: str):
        super().__init__(message, status_code=404, error_code="not_found")


class ValidationError(AppError):
    """Raised when a business action fails input or state validation."""

    def __init__(self, message: str):
        super().__init__(message, status_code=422, error_code="validation_error")


class ConflictError(AppError):
    """Raised when current state conflicts with the requested operation."""

    def __init__(self, message: str):
        super().__init__(message, status_code=409, error_code="conflict")


class UnauthorizedError(AppError):
    """Raised when an operation is not permitted for the current identity."""

    def __init__(self, message: str):
        super().__init__(message, status_code=403, error_code="unauthorized")


class AIServiceError(AppError):
    """Raised when an AI provider cannot complete a request."""

    def __init__(self, message: str):
        super().__init__(message, status_code=503, error_code="ai_service_unavailable")


class IntegrationError(AppError):
    """Raised when a configured external catalog cannot serve usable data."""

    def __init__(self, message: str):
        super().__init__(message, status_code=502, error_code="integration_error")
