-- F6: cabeceras y lineas del historico completo; no son importaciones incrementales.
ALTER TABLE etl_runs ADD COLUMN orders_sha256 CHAR(64) CHARACTER SET ascii NULL;

CREATE TABLE IF NOT EXISTS orders (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    source_order_id VARCHAR(64) COLLATE utf8mb4_bin NOT NULL,
    order_date DATE NOT NULL,
    customer VARCHAR(255) NULL,
    channel VARCHAR(16) COLLATE utf8mb4_bin NOT NULL,
    status VARCHAR(16) COLLATE utf8mb4_bin NOT NULL,
    has_rejected_lines BOOLEAN NOT NULL,
    last_run_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    CONSTRAINT uq_orders_source UNIQUE (source_order_id),
    CONSTRAINT fk_orders_run FOREIGN KEY (last_run_id) REFERENCES etl_runs(id),
    CONSTRAINT chk_orders_channel CHECK (channel IN ('B2B', 'B2C', 'marketplace')),
    CONSTRAINT chk_orders_status CHECK (status IN ('COMPLETADO', 'ENVIADO', 'CANCELADO', 'PENDIENTE', 'DEVUELTO')),
    CONSTRAINT chk_orders_partial CHECK (has_rejected_lines IN (0, 1)),
    INDEX idx_orders_status_date (status, order_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS order_lines (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT UNSIGNED NOT NULL,
    product_id BIGINT UNSIGNED NOT NULL,
    line_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    quantity BIGINT NOT NULL,
    unit_price DECIMAL(18,4) NOT NULL,
    discount DECIMAL(9,6) NOT NULL,
    source_locator VARCHAR(255) NOT NULL,
    last_run_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    CONSTRAINT uq_order_line UNIQUE (order_id, line_key),
    CONSTRAINT fk_line_order FOREIGN KEY (order_id) REFERENCES orders(id),
    CONSTRAINT fk_line_product FOREIGN KEY (product_id) REFERENCES products(id),
    CONSTRAINT fk_line_run FOREIGN KEY (last_run_id) REFERENCES etl_runs(id),
    CONSTRAINT chk_line_quantity CHECK (quantity <> 0),
    CONSTRAINT chk_line_price CHECK (unit_price > 0),
    CONSTRAINT chk_line_discount CHECK (discount >= 0 AND discount <= 1),
    INDEX idx_lines_product_order (product_id, order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
