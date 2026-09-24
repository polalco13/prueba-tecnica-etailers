-- F5: instantanea completa por almacen; las reservas no reducen quantity.
ALTER TABLE etl_runs ADD COLUMN stock_sha256 CHAR(64) CHARACTER SET ascii NULL;

CREATE TABLE IF NOT EXISTS stock_by_warehouse (
    product_id BIGINT UNSIGNED NOT NULL,
    warehouse_code VARCHAR(64) COLLATE utf8mb4_bin NOT NULL,
    quantity BIGINT NOT NULL,
    reserved BIGINT NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    last_run_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    PRIMARY KEY (product_id, warehouse_code),
    CONSTRAINT fk_stock_product FOREIGN KEY (product_id) REFERENCES products(id),
    CONSTRAINT fk_stock_run FOREIGN KEY (last_run_id) REFERENCES etl_runs(id),
    CONSTRAINT chk_stock_quantities CHECK (quantity >= 0 AND reserved >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
