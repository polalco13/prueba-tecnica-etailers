-- F10: resumen inmutable y auditoria de entrega; no contiene secretos del webhook.
ALTER TABLE etl_runs ADD COLUMN make_summary JSON NULL;
ALTER TABLE etl_runs ADD COLUMN make_attempts INT UNSIGNED NOT NULL DEFAULT 0;
ALTER TABLE etl_runs ADD COLUMN make_error_code VARCHAR(64) NULL;
ALTER TABLE etl_runs ADD COLUMN make_last_attempt_at DATETIME(6) NULL;
ALTER TABLE etl_runs ADD COLUMN make_accepted_at DATETIME(6) NULL;
