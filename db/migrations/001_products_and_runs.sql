-- F4: catalogo y auditoria. Aplicar con python -m src.db migrate.
CREATE TABLE IF NOT EXISTS etl_runs (
    id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    finished_at DATETIME(6) NULL,
    status VARCHAR(16) NOT NULL,
    phase VARCHAR(32) NOT NULL,
    error_code VARCHAR(64) NULL,
    csv_sha256 CHAR(64) CHARACTER SET ascii NULL,
    xml_sha256 CHAR(64) CHARACTER SET ascii NULL,
    rules_version VARCHAR(32) NOT NULL,
    counters JSON NULL,
    make_status VARCHAR(20) NOT NULL DEFAULT 'not_applicable',
    CONSTRAINT chk_run_status CHECK (status IN ('running', 'completed', 'failed')),
    CONSTRAINT chk_run_phase CHECK (phase IN ('extract', 'publish')),
    INDEX idx_runs_started (started_at, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS products (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(64) COLLATE utf8mb4_bin NOT NULL,
    ean VARCHAR(13) NULL,
    name VARCHAR(255) NULL,
    brand VARCHAR(255) NULL,
    category VARCHAR(255) NULL,
    brand_key VARCHAR(255) COLLATE utf8mb4_bin NULL,
    category_key VARCHAR(255) COLLATE utf8mb4_bin NULL,
    base_cost DECIMAL(18,4) NULL,
    net_cost DECIMAL(18,4) NULL,
    pvp DECIMAL(18,4) NULL,
    tax_rate DECIMAL(9,6) NULL,
    weight_kg DECIMAL(18,4) NULL,
    listed_on DATE NULL,
    description TEXT NULL,
    price_origin VARCHAR(32) NULL,
    category_discount DECIMAL(9,6) NULL,
    brand_discount DECIMAL(9,6) NULL,
    is_historical BOOLEAN NOT NULL DEFAULT FALSE,
    in_catalog BOOLEAN NOT NULL DEFAULT TRUE,
    stock_total BIGINT NULL,
    stock_status VARCHAR(16) NOT NULL DEFAULT 'unknown',
    stock_as_of DATETIME(6) NULL,
    last_run_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    CONSTRAINT uq_products_sku UNIQUE (sku),
    CONSTRAINT fk_products_run FOREIGN KEY (last_run_id) REFERENCES etl_runs(id),
    CONSTRAINT chk_products_state CHECK (
        (in_catalog = 1 AND is_historical = 0 AND name IS NOT NULL
         AND brand IS NOT NULL AND category IS NOT NULL
         AND net_cost IS NOT NULL AND net_cost > 0 AND pvp IS NOT NULL AND pvp > 0)
        OR (in_catalog = 0 AND is_historical = 1 AND base_cost IS NULL
            AND net_cost IS NULL AND pvp IS NULL AND stock_total IS NULL)
    ),
    CONSTRAINT chk_products_prices CHECK (
        (base_cost IS NULL OR base_cost > 0) AND
        (net_cost IS NULL OR net_cost > 0) AND
        (pvp IS NULL OR pvp > 0)
    ),
    CONSTRAINT chk_products_ratios CHECK (
        (tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 1)) AND
        (category_discount IS NULL OR (category_discount >= 0 AND category_discount <= 1)) AND
        (brand_discount IS NULL OR (brand_discount >= 0 AND brand_discount <= 1))
    ),
    CONSTRAINT chk_products_weight CHECK (weight_kg IS NULL OR weight_kg >= 0),
    CONSTRAINT chk_products_stock CHECK (
        (stock_status = 'unknown' AND stock_total IS NULL AND stock_as_of IS NULL)
        OR (stock_status = 'known' AND stock_total IS NOT NULL
            AND stock_total >= 0 AND stock_as_of IS NOT NULL)
        OR (stock_status = 'invalid' AND stock_total IS NULL)
    ),
    INDEX idx_products_category (category_key, sku)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS rejections (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    run_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    source VARCHAR(32) NOT NULL,
    record_locator VARCHAR(255) NOT NULL,
    entity_key VARCHAR(255) NULL,
    reason_code VARCHAR(64) NOT NULL,
    field_name VARCHAR(64) NOT NULL DEFAULT '',
    action VARCHAR(20) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    detail VARCHAR(512) NOT NULL,
    raw_excerpt VARCHAR(512) NULL,
    CONSTRAINT fk_rejections_run FOREIGN KEY (run_id) REFERENCES etl_runs(id),
    CONSTRAINT uq_rejection UNIQUE (run_id, source, record_locator, reason_code, field_name),
    CONSTRAINT chk_rejection_action CHECK (
        action IN ('normalize', 'reject_row', 'drop_field', 'deduplicate', 'warn', 'fail_run')
    ),
    CONSTRAINT chk_rejection_severity CHECK (severity IN ('info', 'warning', 'error')),
    INDEX idx_rejection_reason (run_id, reason_code),
    INDEX idx_rejection_entity (source, entity_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
