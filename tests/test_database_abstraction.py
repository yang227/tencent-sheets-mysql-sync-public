"""
Tests for the unified database abstraction layer,
exception hierarchy, and PostgreSQL service.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.db_exception import (
    DatabaseServiceError,
    DatabaseConnectionError,
    DatabaseQueryError,
    DatabaseTimeoutError,
    DatabaseIntegrityError,
    DatabaseConfigurationError,
    IdentifierValidationError,
    DatabaseTypeValidationError,
    handle_service_exception,
)
from app.services.database_service import (
    DatabaseService,
    validate_identifier,
    validate_identifier_list,
    validate_data_type,
    create_database_service,
)


# ─── Identifier validation ────────────────────────────────────────

class TestValidateIdentifier:
    def test_valid_name(self):
        assert validate_identifier("my_table") == "my_table"

    def test_valid_with_underscore(self):
        assert validate_identifier("_private") == "_private"

    def test_empty_raises(self):
        with pytest.raises(IdentifierValidationError):
            validate_identifier("")

    def test_too_long_raises(self):
        with pytest.raises(IdentifierValidationError):
            validate_identifier("a" * 64)

    def test_starts_with_digit_raises(self):
        with pytest.raises(IdentifierValidationError):
            validate_identifier("123abc")

    def test_special_chars_raises(self):
        with pytest.raises(IdentifierValidationError):
            validate_identifier("drop;table")

    def test_strips_backticks(self):
        assert validate_identifier("`my_table`") == "my_table"

    def test_allow_hyphen(self):
        assert validate_identifier("my-db", allow_hyphen=True) == "my-db"

    def test_no_hyphen_by_default(self):
        with pytest.raises(IdentifierValidationError):
            validate_identifier("my-db")


class TestValidateIdentifierList:
    def test_valid_list(self):
        result = validate_identifier_list(["a", "b", "c"])
        assert result == ["a", "b", "c"]

    def test_invalid_in_list_raises(self):
        with pytest.raises(IdentifierValidationError):
            validate_identifier_list(["valid", "123invalid"])


# ─── Type validation ──────────────────────────────────────────────

class TestValidateDataType:
    def test_varchar_with_length(self):
        assert validate_data_type("VARCHAR(255)") == "VARCHAR(255)"

    def test_simple_int(self):
        assert validate_data_type("INT") == "INT"

    def test_empty_raises(self):
        with pytest.raises(DatabaseTypeValidationError):
            validate_data_type("")

    def test_disallowed_type_raises(self):
        with pytest.raises(DatabaseTypeValidationError):
            validate_data_type("EVIL_TYPE")

    def test_sql_injection_in_type_raises(self):
        with pytest.raises(DatabaseTypeValidationError):
            validate_data_type("INT; DROP TABLE")


# ─── Exception hierarchy ──────────────────────────────────────────

class TestExceptionHierarchy:
    def test_all_inherit_from_base(self):
        base = DatabaseServiceError
        assert issubclass(DatabaseConnectionError, base)
        assert issubclass(DatabaseQueryError, base)
        assert issubclass(DatabaseTimeoutError, base)
        assert issubclass(DatabaseIntegrityError, base)
        assert issubclass(DatabaseConfigurationError, base)
        assert issubclass(IdentifierValidationError, base)
        assert issubclass(DatabaseTypeValidationError, base)

    def test_exception_carries_context(self):
        exc = DatabaseConnectionError(
            "Connection refused", db_type="postgresql", query="SELECT 1"
        )
        assert exc.db_type == "postgresql"
        assert exc.query == "SELECT 1"

    def test_exception_preserves_cause(self):
        original = OSError("Network unreachable")
        exc = DatabaseConnectionError("Failed", cause=original)
        assert exc.cause is original


# ─── handle_service_exception ─────────────────────────────────────

class TestHandleServiceException:
    def test_http_exception_passthrough(self):
        from fastapi import HTTPException
        original = HTTPException(status_code=404, detail="Not found")
        result = handle_service_exception(original)
        assert result.status_code == 404
        assert result is original

    def test_connection_error_maps_503(self):
        exc = DatabaseConnectionError("Refused", db_type="mysql")
        result = handle_service_exception(exc)
        assert result.status_code == 503

    def test_timeout_maps_504(self):
        exc = DatabaseTimeoutError("Timeout", db_type="postgresql")
        result = handle_service_exception(exc)
        assert result.status_code == 504

    def test_integrity_maps_409(self):
        exc = DatabaseIntegrityError("Duplicate key", db_type="mysql")
        result = handle_service_exception(exc)
        assert result.status_code == 409

    def test_identifier_validation_maps_400(self):
        exc = IdentifierValidationError("Bad name")
        result = handle_service_exception(exc)
        assert result.status_code == 400

    def test_query_error_maps_500(self):
        exc = DatabaseQueryError("Syntax error", db_type="mysql")
        result = handle_service_exception(exc)
        assert result.status_code == 500

    def test_unknown_maps_500(self):
        exc = ValueError("Something unexpected")
        result = handle_service_exception(exc)
        assert result.status_code == 500

    def test_tencent_404_maps_404(self):
        from app.services.tencent_api import TencentAPIError
        exc = TencentAPIError(404, "Not found")
        result = handle_service_exception(exc)
        assert result.status_code == 404

    def test_tencent_403_maps_403(self):
        from app.services.tencent_api import TencentAPIError
        exc = TencentAPIError(403, "Forbidden")
        result = handle_service_exception(exc)
        assert result.status_code == 403

    def test_tencent_other_maps_502(self):
        from app.services.tencent_api import TencentAPIError
        exc = TencentAPIError(500, "Server error")
        result = handle_service_exception(exc)
        assert result.status_code == 502

    def test_mapping_error_maps_400(self):
        from app.services.mapping import MappingError
        exc = MappingError("Bad mapping")
        result = handle_service_exception(exc)
        assert result.status_code == 400


# ─── Factory ──────────────────────────────────────────────────────

class TestCreateDatabaseService:
    def test_mysql_type(self):
        with patch("app.services.mysql_service.MySQLService.__init__", return_value=None):
            svc = create_database_service("mysql")
            assert svc.DB_TYPE == "mysql"

    def test_pg_aliases(self):
        with patch("app.services.postgresql_service.PostgreSQLService.__init__", return_value=None):
            for alias in ("postgresql", "postgres", "pg"):
                svc = create_database_service(alias)
                assert svc.DB_TYPE == "postgresql"

    def test_unsupported_raises(self):
        with pytest.raises(DatabaseConfigurationError):
            create_database_service("oracle")


# ─── DatabaseService abstract ─────────────────────────────────────

class TestDatabaseServiceAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            DatabaseService()

    def test_compute_row_hash(self):
        h1 = DatabaseService.compute_row_hash([1, "hello", None])
        h2 = DatabaseService.compute_row_hash([1, "hello", None])
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_compute_row_hash_deterministic(self):
        h1 = DatabaseService.compute_row_hash(["a", "b"])
        h2 = DatabaseService.compute_row_hash(["b", "a"])
        assert h1 != h2  # Order matters


# ─── PostgreSQL type mapping ──────────────────────────────────────

class TestPostgreSQLTypeMapping:
    def test_mysql_to_pg_varchar(self):
        from app.services.postgresql_service import _mysql_to_pg_type
        assert _mysql_to_pg_type("VARCHAR(255)") == "VARCHAR(255)"

    def test_mysql_to_pg_int(self):
        from app.services.postgresql_service import _mysql_to_pg_type
        assert _mysql_to_pg_type("INT") == "INTEGER"

    def test_mysql_to_pg_datetime(self):
        from app.services.postgresql_service import _mysql_to_pg_type
        assert _mysql_to_pg_type("DATETIME") == "TIMESTAMP"

    def test_mysql_to_pg_json(self):
        from app.services.postgresql_service import _mysql_to_pg_type
        assert _mysql_to_pg_type("JSON") == "JSONB"

    def test_mysql_to_pg_blob(self):
        from app.services.postgresql_service import _mysql_to_pg_type
        assert _mysql_to_pg_type("BLOB") == "BYTEA"

    def test_mysql_to_pg_tinyint(self):
        from app.services.postgresql_service import _mysql_to_pg_type
        assert _mysql_to_pg_type("TINYINT") == "SMALLINT"

    def test_mysql_to_pg_decimal(self):
        from app.services.postgresql_service import _mysql_to_pg_type
        assert _mysql_to_pg_type("DECIMAL(10,2)") == "NUMERIC(10,2)"