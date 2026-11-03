class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400, error_code: str = "app_error"):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class NotFoundError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=404, error_code="not_found")


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=422, error_code="validation_error")


class ConflictError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=409, error_code="conflict")


class UnauthorizedError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=403, error_code="unauthorized")


class AIServiceError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=503, error_code="ai_service_unavailable")


class IntegrationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=502, error_code="integration_error")
