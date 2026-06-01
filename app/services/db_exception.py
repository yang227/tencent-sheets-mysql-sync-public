"""
Unified database exception hierarchy.

All database-related errors across MySQL and PostgreSQL converge here,
making it easy for callers to handle errors uniformly regardless of backend.

Exception tree:

    DatabaseServiceError (base)
    +-- DatabaseConnectionError       (cannot reach / auth failure)
    +-- DatabaseQueryError            (SQL execution failure)
    +-- DatabaseTimeoutError          (query or connect timeout)
    +-- DatabaseIntegrityError        (constraint violation / duplicate)
    +-- DatabaseConfigurationError    (bad config / missing credentials)
    +-- IdentifierValidationError     (SQL injection defence)
    +-- DatabaseTypeValidationError   (disallowed column type)
"""
from typing import Optional


class DatabaseServiceError(Exception):
    """Base exception for all database service errors."""

    def __init__(
        self,
        message: str,
        db_type: str = "",
        query: str = "",
        cause: Optional[Exception] = None,
    ):
        self.db_type = db_type
        self.query = query[:200] if query else ""
        self.cause = cause
        super().__init__(message)


class DatabaseConnectionError(DatabaseServiceError):
    """Cannot establish or authenticate a database connection."""
    pass


class DatabaseQueryError(DatabaseServiceError):
    """A SQL query failed during execution."""
    pass


class DatabaseTimeoutError(DatabaseServiceError):
    """A database operation timed out (connect or query)."""
    pass


class DatabaseIntegrityError(DatabaseServiceError):
    """Constraint violation, duplicate key, FK violation, etc."""
    pass


class DatabaseConfigurationError(DatabaseServiceError):
    """Mis-configured credentials, missing parameters, etc."""
    pass


class IdentifierValidationError(DatabaseServiceError):
    """An identifier (table/column name) failed safety validation."""
    pass


class DatabaseTypeValidationError(DatabaseServiceError):
    """A column data type is not in the allowed whitelist."""
    pass


# ─── Router-level helper ──────────────────────────────────────────
# Maps specific exception types to HTTP status codes so every router
# can share the same mapping logic instead of ad-hoc try/except chains.

from fastapi import HTTPException


def handle_service_exception(exc: Exception, context: str = "") -> HTTPException:
    """
    Convert a service-layer exception into a FastAPI HTTPException
    with the most appropriate status code.

    Returns an HTTPException that the caller should ``raise``.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Already an HTTPException — pass through unchanged
    if isinstance(exc, HTTPException):
        return exc

    # ─── Database errors ──────────────────────────────────────────
    if isinstance(exc, DatabaseConnectionError):
        logger.error("%s | DB connection error: %s", context, exc)
        return HTTPException(status_code=503, detail=str(exc))

    if isinstance(exc, DatabaseTimeoutError):
        logger.error("%s | DB timeout: %s", context, exc)
        return HTTPException(status_code=504, detail=str(exc))

    if isinstance(exc, DatabaseIntegrityError):
        logger.warning("%s | DB integrity: %s", context, exc)
        return HTTPException(status_code=409, detail=str(exc))

    if isinstance(exc, IdentifierValidationError):
        logger.warning("%s | Invalid identifier: %s", context, exc)
        return HTTPException(status_code=400, detail=str(exc))

    if isinstance(exc, DatabaseTypeValidationError):
        logger.warning("%s | Invalid type: %s", context, exc)
        return HTTPException(status_code=400, detail=str(exc))

    if isinstance(exc, DatabaseConfigurationError):
        logger.error("%s | DB config error: %s", context, exc)
        return HTTPException(status_code=400, detail=str(exc))

    if isinstance(exc, DatabaseQueryError):
        logger.error("%s | DB query error: %s", context, exc)
        return HTTPException(status_code=500, detail=str(exc))

    if isinstance(exc, DatabaseServiceError):
        logger.error("%s | DB error: %s", context, exc)
        return HTTPException(status_code=500, detail=str(exc))

    # ─── Tencent API errors ───────────────────────────────────────
    from app.services.tencent_api import TencentAPIError
    if isinstance(exc, TencentAPIError):
        if exc.code == 404:
            logger.warning("%s | Tencent 404: %s", context, exc)
            return HTTPException(status_code=404, detail=str(exc))
        if exc.code == 403:
            logger.warning("%s | Tencent 403: %s", context, exc)
            return HTTPException(status_code=403, detail=str(exc))
        logger.error("%s | Tencent API error [%d]: %s", context, exc.code, exc)
        return HTTPException(status_code=502, detail=str(exc))

    # ─── Mapping errors ───────────────────────────────────────────
    from app.services.mapping import MappingError
    if isinstance(exc, MappingError):
        logger.warning("%s | Mapping error: %s", context, exc)
        return HTTPException(status_code=400, detail=str(exc))

    # ─── Sync engine errors ───────────────────────────────────────
    from app.services.sync_engine import SyncEngineError
    if isinstance(exc, SyncEngineError):
        logger.error("%s | Sync error: %s", context, exc)
        return HTTPException(status_code=500, detail=str(exc))

    # ─── Fallback ─────────────────────────────────────────────────
    logger.exception("%s | Unexpected error: %s", context, exc)
    return HTTPException(status_code=500, detail=f"Internal error: {exc}")