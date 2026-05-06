"""
Security tests for SQL injection protection.
Tests the identifier validation and MySQL type validation.
"""
import pytest
from app.services.mysql_service import (
    _validate_identifier,
    _validate_mysql_type,
)


class TestValidateIdentifier:
    """Test cases for _validate_identifier function."""

    def test_valid_identifier(self):
        """Test valid identifier passes validation."""
        assert _validate_identifier("users") == "users"
        assert _validate_identifier("_private") == "_private"
        assert _validate_identifier("table123") == "table123"
        assert _validate_identifier("my_table") == "my_table"

    def test_valid_identifier_with_backticks(self):
        """Test identifier with backticks is cleaned."""
        assert _validate_identifier("`users`") == "users"
        assert _validate_identifier("`_private`") == "_private"

    def test_empty_identifier(self):
        """Test empty identifier raises ValueError."""
        with pytest.raises(ValueError, match="Identifier cannot be empty"):
            _validate_identifier("")

    def test_none_identifier(self):
        """Test None identifier raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_identifier(None)

    def test_too_long_identifier(self):
        """Test identifier longer than 64 characters raises ValueError."""
        long_name = "a" * 65
        with pytest.raises(ValueError, match="too long"):
            _validate_identifier(long_name)

    def test_sql_injection_single_quote(self):
        """Test single quote injection is rejected."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            _validate_identifier("users'; DROP TABLE users; --")

    def test_sql_injection_double_quote(self):
        """Test double quote injection is rejected."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            _validate_identifier('users" OR "1"="1')

    def test_sql_injection_semicolon(self):
        """Test semicolon injection is rejected."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            _validate_identifier("users; DROP TABLE users")

    def test_sql_injection_comment(self):
        """Test SQL comment injection is rejected."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            _validate_identifier("users--comment")

    def test_sql_injection_union(self):
        """Test UNION injection is rejected."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            _validate_identifier("users UNION SELECT")

    def test_identifier_with_hyphen_not_allowed(self):
        """Test hyphen is not allowed by default."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            _validate_identifier("my-table")

    def test_identifier_with_hyphen_allowed(self):
        """Test hyphen is allowed when allow_hyphen=True."""
        # Database names can have hyphens
        result = _validate_identifier("my-database", allow_hyphen=True)
        assert result == "my-database"

    def test_identifier_starts_with_number(self):
        """Test identifier starting with number is rejected."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            _validate_identifier("123table")


class TestValidateMysqlType:
    """Test cases for _validate_mysql_type function."""

    def test_valid_types(self):
        """Test valid MySQL types pass validation."""
        assert _validate_mysql_type("VARCHAR(255)") == "VARCHAR(255)"
        assert _validate_mysql_type("INT") == "INT"
        assert _validate_mysql_type("DECIMAL(10,2)") == "DECIMAL(10,2)"
        assert _validate_mysql_type("TEXT") == "TEXT"
        assert _validate_mysql_type("DATETIME") == "DATETIME"
        assert _validate_mysql_type("BIGINT") == "BIGINT"

    def test_valid_types_case_insensitive(self):
        """Test type validation is case insensitive."""
        assert _validate_mysql_type("varchar(255)") == "varchar(255)"
        assert _validate_mysql_type("Int") == "Int"

    def test_invalid_type(self):
        """Test invalid MySQL type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid data type"):
            _validate_mysql_type("INVALID_TYPE")

    def test_type_with_sql_injection(self):
        """Test type with SQL injection is rejected."""
        with pytest.raises(ValueError, match="Invalid data type"):
            _validate_mysql_type("VARCHAR(255); DROP TABLE users;")

    def test_type_with_comment(self):
        """Test type with SQL comment is rejected."""
        with pytest.raises(ValueError, match="Invalid data type"):
            _validate_mysql_type("VARCHAR(255)--comment")

    def test_empty_type(self):
        """Test empty type raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_mysql_type("")

    def test_none_type(self):
        """Test None type raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_mysql_type(None)


class TestSqlInjectionInMethods:
    """Test that MySQLService methods properly validate inputs."""

    def test_validate_identifier_called_in_list_tables(self):
        """Test that list_tables validates database name."""
        from unittest.mock import patch
        from app.services.mysql_service import MySQLService
        
        service = MySQLService()
        
        # Mock execute to avoid DB connection
        service.execute = lambda q, p=None: []
        
        # Test with invalid database name
        with patch('app.services.mysql_service._validate_identifier') as mock_val:
            mock_val.side_effect = ValueError("Invalid identifier")
            try:
                service.list_tables("invalid;name")
            except ValueError:
                pass
            
            # Verify validation was called
            assert mock_val.called
