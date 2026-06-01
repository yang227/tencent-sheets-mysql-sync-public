-- PostgreSQL configs table (stored in metadata MySQL)
CREATE TABLE IF NOT EXISTS postgresql_configs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(128) NOT NULL UNIQUE,
    host VARCHAR(256) NOT NULL,
    port INT NOT NULL DEFAULT 5432,
    username VARCHAR(128) NOT NULL,
    password_encrypted TEXT NOT NULL,
    database_name VARCHAR(128) NOT NULL,
    schema_name VARCHAR(128) DEFAULT 'public',
    description VARCHAR(512) DEFAULT NULL,
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_tested_at DATETIME DEFAULT NULL,
    test_status ENUM('untested', 'success', 'failed') DEFAULT 'untested',
    test_message TEXT DEFAULT NULL,
    INDEX idx_name (name),
    INDEX idx_active (is_active),
    INDEX idx_created (created_at)
);

-- Add db_type and postgresql_config_id to sync_configs if not present
SET @add_db_type = (
    SELECT IF(
        EXISTS (
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'sync_configs'
              AND COLUMN_NAME = 'db_type'
        ),
        'SELECT 1',
        'ALTER TABLE sync_configs ADD COLUMN db_type VARCHAR(16) NOT NULL DEFAULT ''mysql'' AFTER `database`'
    )
);
PREPARE stmt FROM @add_db_type;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_pg_config_id = (
    SELECT IF(
        EXISTS (
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'sync_configs'
              AND COLUMN_NAME = 'postgresql_config_id'
        ),
        'SELECT 1',
        'ALTER TABLE sync_configs ADD COLUMN postgresql_config_id BIGINT DEFAULT NULL AFTER db_type'
    )
);
PREPARE stmt FROM @add_pg_config_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_idx_pg_config_id = (
    SELECT IF(
        EXISTS (
            SELECT 1 FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'sync_configs'
              AND INDEX_NAME = 'idx_postgresql_config_id'
        ),
        'SELECT 1',
        'ALTER TABLE sync_configs ADD INDEX idx_postgresql_config_id (postgresql_config_id)'
    )
);
PREPARE stmt FROM @add_idx_pg_config_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;