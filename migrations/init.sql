CREATE TABLE IF NOT EXISTS sync_configs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    spreadsheet_id VARCHAR(128) NOT NULL,
    sheet_id VARCHAR(64) NOT NULL,
    table_name VARCHAR(128) NOT NULL,
    `database` VARCHAR(128) NOT NULL DEFAULT '',
    mapping_json JSON NOT NULL,
    sync_direction ENUM('to_mysql', 'from_mysql', 'bidirectional') DEFAULT 'bidirectional',
    poll_interval INT DEFAULT 30,
    last_sync_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active TINYINT(1) DEFAULT 1,
    UNIQUE KEY uk_spreadsheet_sheet (spreadsheet_id, sheet_id),
    INDEX idx_active (is_active)
);

CREATE TABLE IF NOT EXISTS sync_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    config_id BIGINT NOT NULL,
    direction ENUM('to_mysql', 'from_mysql', 'bidirectional') NOT NULL,
    rows_affected INT DEFAULT 0,
    rows_new INT DEFAULT 0,
    rows_updated INT DEFAULT 0,
    rows_skipped INT DEFAULT 0,
    status ENUM('running', 'success', 'partial', 'failed') DEFAULT 'running',
    error_message TEXT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_config_time (config_id, created_at)
);

CREATE TABLE IF NOT EXISTS change_tracking (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    config_id BIGINT NOT NULL,
    source_row_key VARCHAR(256) NOT NULL,
    source_hash VARCHAR(64) NOT NULL,
    prev_value TEXT,
    last_sync_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    source ENUM('tencent', 'mysql') NOT NULL,
    INDEX idx_config_row (config_id, source_row_key),
    UNIQUE KEY uk_config_row (config_id, source_row_key)
);
