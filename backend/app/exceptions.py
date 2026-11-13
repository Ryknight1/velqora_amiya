"""Application errors. Messages are written to be safe to show to end users."""
from __future__ import annotations

from typing import Any, Optional


class VelQoraError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, code: Optional[str] = None, status_code: Optional[int] = None,
                 details: Any = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details


class NotFoundError(VelQoraError):
    status_code = 404
    code = "not_found"


class ConflictError(VelQoraError):
    status_code = 409
    code = "conflict"


class AuthError(VelQoraError):
    status_code = 401
    code = "unauthorized"


class ValidationFailure(VelQoraError):
    status_code = 422
    code = "validation_error"


class RateLimitedError(VelQoraError):
    status_code = 429
    code = "rate_limited"


class ServiceNotConfigured(VelQoraError):
    status_code = 503
    code = "service_not_configured"


class ExternalServiceError(VelQoraError):
    """An upstream dependency (Tavily / Bifrost) failed."""
    status_code = 502
    code = "upstream_error"


class UpstreamQuotaError(ExternalServiceError):
    status_code = 429
    code = "upstream_quota_exceeded"


class UpstreamAuthError(ExternalServiceError):
    status_code = 502
    code = "upstream_auth_failed"
