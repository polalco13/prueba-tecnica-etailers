# Integración Make

[Blueprint exportado](escenario.blueprint.json) del escenario real, saneado de webhook, conexiones, hoja y destinatario. Código de llamada: [make_client.py](../src/etl/make_client.py); resumen persistido antes del envío ([ADR 005](../docs/adr/005-persisted-make-delivery.md)).

## Disparador y decisiones

Tras publicar el ETL, envía `etl-summary-v1`: ejecución/fechas, productos, contadores por fuente, motivos de rechazo, facturación del mes anterior y bajo mínimos. Importes como texto decimal; moneda/IVA sin confirmar. Sin clientes ni líneas originales. Ejemplos [normal](examples/summary.synthetic.json) y [con alerta](examples/alert.synthetic.json) sintéticos.

Filtro inicial: versión correcta, estado `completed` y `run_id` informado. Procesamiento secuencial e histórico primero:

1. **Histórico:** busca `run_id` en Sheets y añade fila solo si no existe.
2. **Alerta:** `rows_rejected > rejection_threshold OR low_stock_count > 0`; busca la fila y envía Gmail solo con `email_sent_at` vacío; después actualiza esa marca.

Duplicados/avisos no disparan por sí solos alerta. Fallos completos del ETL quedan en auditoría local y no generan contrato de éxito.

## Importar y configurar

1. Importar el blueprint en un escenario nuevo y desactivado.
2. Crear/seleccionar Custom webhook [1], autorizar Sheets [3/9/15/17] y Gmail [16]. Asignar hoja `ejecuciones` y destinatario propio; revisar el correo antes de ejecutar.
3. Crear cabeceras A–O en este orden:

```text
run_id | finished_at | status | as_of | products_loaded | rows_rejected |
rows_json | rejected_by_reason_json | previous_month | revenue_previous_month |
low_stock_count | low_stock_products_json | rejection_threshold | alert_required | email_sent_at
```

4. Mantener **Process data in order**, búsquedas exactas por ID con límite 1 y entrada **Raw** en ambas escrituras. JSON [10/13/14] serializa `rows`, `rejected_by_reason` y `low_stock_products` por separado a G/H/L.

Una búsqueda sin coincidencias emite un bundle vacío; el agregador [7] puede tener longitud 1. «Ejecución nueva» comprueba número de fila, no longitud:

```text
{{ifempty(get(7.array; "1.__ROW_NUMBER__"); 0)}}
Numeric operators: Equal to
0
```

«Correo pendiente»: `15. Row number > 0` AND `15. email_sent_at (O) Does not exist`. Update a Cell [17], después de Gmail, usa celda `O{{15.__ROW_NUMBER__}}` y valor:

```text
{{formatDate(now; "YYYY-MM-DD HH:mm:ss"; "UTC")}} UTC
```

## Configuración local y reenvío

Aplicar `.venv/bin/python -m src.db migrate` hasta `004_make_delivery`. Variables del entorno privado:

| Variable | Inicial | Uso |
| --- | --- | --- |
| `MAKE_WEBHOOK_URL` | vacío | HTTPS del webhook; vacío desactiva envío. No versionar ni publicar. |
| `MAKE_TIMEOUT` | 10 | Segundos por operación (1–60). |
| `MAKE_REJECTION_THRESHOLD` | 0 | Umbral absoluto (0–1.000.000); alerta al superarlo. |

```bash
.venv/bin/python -m src.etl
.venv/bin/python -m src.etl --resend-make RUN_ID
```

Reenvía el resumen guardado sin recargar datos. Si ya fue aceptado, `--force` repite el POST tras revisar Make. Sin reintento HTTP automático: timeout puede haber tenido efecto remoto. Código 2 indica entrega no confirmada con negocio publicado; estado/intentos en `etl_runs`.

## Cierre y límites de verificación

El 27/09/2026 el ETL real `c1a93f67-6990-4748-8efa-c18bc6777b42` publicó **115 productos, 72 rechazadas y 12 bajo mínimos**, con facturación de agosto **56.696,84**. La [captura](capturas/f10-real-etl-destinations.png) muestra escenario y ambas rutas completadas. Correo recibido y fila de Sheets aportados por el usuario: una ejecución, valores/JSON contrastados y `email_sent_at=2026-09-27 15:34:53 UTC`.

También se observaron caso sin alerta, rechazo de contrato y bloqueo de reenvío. Capturas intermedias retiradas de la entrega; disponibles en historial Git.

**Límites:** HTTP 2xx confirma recepción, no destinos; si Gmail envía y falla la marca, puede duplicar correo al reenviar. Recuperación externa/concurrencia no probadas. Importación confirmada; conexiones/ejecución de esa copia sin verificar. La evidencia corresponde al escenario original.

Referencias: [blueprints](https://help.make.com/blueprints), [Google Sheets](https://apps.make.com/google-sheets-modules).
