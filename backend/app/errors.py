"""Domain errors that the API layer maps to HTTP responses."""


class AppError(Exception):
    """Base error with an HTTP status and a user-facing message."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


class UpstreamError(AppError):
    status_code = 502
    code = "upstream_error"


class LLMOutputError(AppError):
    status_code = 502
    code = "llm_invalid_output"


class ConfigError(AppError):
    status_code = 500
    code = "config_error"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"
