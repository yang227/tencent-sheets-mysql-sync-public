# Database Abstraction + PostgreSQL Support + Exception Optimization

**Date**: 2026-06-01  
**Status**: Approved  

## Goals

1. Introduce a DatabaseService abstract base class that captures all shared logic between MySQL and PostgreSQL (connection pooling, CRUD, change tracking, identifier validation, etc.)
2. Implement PostgreSQLService as a concrete subclass using psycopg2 (or psycopg v3).
3. Refactor MySQLService to inherit from DatabaseService, overriding only MySQL-specific behavior.
4. Unify all exception handling across the codebase: eliminate bare except Exception catches, ensure every error path has a specific exception type, structured logging, and proper HTTP status mapping.
5. Update SyncEngine to accept any DatabaseService and select MySQL vs PostgreSQL based on config.

## Architecture

### New files

`
app/
  services/
    database_service.py        # Abstract base class
    postgresql_service.py      # PostgreSQL implementation
    db_exception.py            # Unified exception hierarchy
  models/
    postgresql_config_models.py  # Pydantic models for pg config CRUD
  routers/
    postgresql_config_router.py  # API endpoints for pg config management
`

### Modified files

- pp/services/mysql_service.py — inherits from DatabaseService
- pp/services/sync_engine.py — uses DatabaseService instead of MySQLService for target DB
- pp/services/sync_engine_enhanced.py — same
- pp/config.py — add db_type field to sync config
- pp/main.py — register new routers
- pp/routers/mysql_browser.py — genericized to db_browser
- pp/routers/sync_router.py — improved exception mapping
- pp/routers/config_router.py — improved exception mapping
- pp/routers/enhanced_router.py — improved exception mapping
- pp/routers/monitoring_router.py — improved exception mapping
- pp/routers/mysql_config_router.py — improved exception mapping
- pp/routers/tencent_config_router.py — improved exception mapping
- pp/routers/workbench_router.py — improved exception mapping
- pp/routers/tencent_helper.py — improved exception mapping
- pp/webhooks/tencent_webhook.py — improved exception mapping
- migrations/add_config_tables.sql — add postgresql_configs table + db_type column on sync_configs
- equirements.txt — add psycopg2-binary>=2.9.0

### Exception Hierarchy (db_exception.py)

`
DatabaseServiceError (base)
├── DatabaseConnectionError
├── DatabaseQueryError
├── DatabaseTimeoutError
├── DatabaseIntegrityError
├── DatabaseConfigurationError
├── IdentifierValidationError
└── DatabaseTypeValidationError
`

Each exception carries db_type, query (when safe), and original cause.

### DatabaseService ABC

`python
class DatabaseService(ABC):
    # Shared: execute(), execute_many(), test_connection(), init_system_tables()
    # Shared: sync_config CRUD, sync_log CRUD, change_tracking CRUD
    # Shared: identifier validation, type validation
    # Abstract: _create_pool(), _get_conn(), _quote_identifier()
    # Abstract: list_databases(), list_tables(), get_table_columns()
    # Abstract: create_data_table(), table_exists()
`

### Config changes

- sync_configs.db_type ENUM('mysql','postgresql') DEFAULT 'mysql'
- New postgresql_configs table (mirrors mysql_configs structure)
- SyncEngine reads db_type and instantiates the correct service via a factory

### Exception optimization rules

1. No bare except: or except Exception: without re-raising as a specific type
2. All router endpoints use a common handle_service_exception() helper that maps:
   - DatabaseConnectionError → 503
   - DatabaseQueryError → 500
   - DatabaseTimeoutError → 504
   - DatabaseIntegrityError → 409
   - IdentifierValidationError → 400
   - TencentAPIError with 404 → 404
   - TencentAPIError with 403 → 403
   - TencentAPIError other → 502
   - MappingError → 400
   - SyncEngineError → 500
   - Unknown → 500 with structured log
3. All logger.error() calls include structured context (config_id, operation, error type)
4. Connection pool lifecycle: explicit close() on shutdown, leak detection on acquire

## Implementation Order

1. db_exception.py — unified exception hierarchy
2. database_service.py — abstract base class
3. Refactor mysql_service.py to inherit from base
4. postgresql_service.py — new service
5. postgresql_config_models.py + postgresql_config_router.py
6. Migration script for postgresql_configs + db_type column
7. Update SyncEngine / SyncEngineEnhanced to use factory
8. Exception sweep: update all routers, services, webhooks
9. Update equirements.txt, config.py, main.py
10. Update tests

## Risks

- MySQL-specific SQL in migrations must remain MySQL-only; PostgreSQL migrations are separate
- The metadata database itself remains MySQL; only the sync target can be PostgreSQL
- psycopg2-binary wheel availability on all target platforms