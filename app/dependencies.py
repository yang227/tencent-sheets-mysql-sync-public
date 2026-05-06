"""
Shared FastAPI dependencies for dependency injection.
"""
from fastapi import Depends
from app.services.mysql_service import get_mysql_service, MySQLService

# Reusable dependency for getting MySQL service instance
def get_db() -> MySQLService:
    """
    FastAPI dependency that returns a MySQLService instance.
    Uses the singleton pattern from mysql_service module.
    """
    return get_mysql_service()
