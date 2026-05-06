CREATE TABLE IF NOT EXISTS mysql_configs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(128) NOT NULL UNIQUE,
    host VARCHAR(256) NOT NULL,
    port INT NOT NULL DEFAULT 3306,
    username VARCHAR(128) NOT NULL,
    password_encrypted TEXT NOT NULL,
    database_name VARCHAR(128) NOT NULL,
    charset VARCHAR(32) DEFAULT 'utf8mb4',
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

CREATE TABLE IF NOT EXISTS tencent_api_configs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(128) NOT NULL UNIQUE,
    app_id VARCHAR(256) NOT NULL,
    open_id VARCHAR(256) NOT NULL,
    access_token_encrypted TEXT NOT NULL,
    description VARCHAR(512) DEFAULT NULL,
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_tested_at DATETIME DEFAULT NULL,
    test_status ENUM('untested', 'success', 'failed') DEFAULT 'untested',
    test_message TEXT DEFAULT NULL,
    token_expires_at DATETIME DEFAULT NULL,
    INDEX idx_name (name),
    INDEX idx_active (is_active),
    INDEX idx_created (created_at)
);

SET @add_mysql_config_id = (
    SELECT IF(
        EXISTS (
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'sync_configs'
              AND COLUMN_NAME = 'mysql_config_id'
        ),
        'SELECT 1',
        'ALTER TABLE sync_configs ADD COLUMN mysql_config_id BIGINT DEFAULT NULL AFTER `database`'
    )
);
PREPARE stmt FROM @add_mysql_config_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_tencent_config_id = (
    SELECT IF(
        EXISTS (
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'sync_configs'
              AND COLUMN_NAME = 'tencent_config_id'
        ),
        'SELECT 1',
        'ALTER TABLE sync_configs ADD COLUMN tencent_config_id BIGINT DEFAULT NULL AFTER mysql_config_id'
    )
);
PREPARE stmt FROM @add_tencent_config_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_idx_mysql_config_id = (
    SELECT IF(
        EXISTS (
            SELECT 1
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'sync_configs'
              AND INDEX_NAME = 'idx_mysql_config_id'
        ),
        'SELECT 1',
        'ALTER TABLE sync_configs ADD INDEX idx_mysql_config_id (mysql_config_id)'
    )
);
PREPARE stmt FROM @add_idx_mysql_config_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_idx_tencent_config_id = (
    SELECT IF(
        EXISTS (
            SELECT 1
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'sync_configs'
              AND INDEX_NAME = 'idx_tencent_config_id'
        ),
        'SELECT 1',
        'ALTER TABLE sync_configs ADD INDEX idx_tencent_config_id (tencent_config_id)'
    )
);
PREPARE stmt FROM @add_idx_tencent_config_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
