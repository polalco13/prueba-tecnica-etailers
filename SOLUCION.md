# Solución

ETL de las cuatro fuentes originales → MySQL → catálogo y panel de negocio. Al terminar una carga, Make registra el resumen en Google Sheets y envía una alerta por Gmail cuando corresponde.

Repositorio: [prueba-tecnica-etailers](https://github.com/polalco13/prueba-tecnica-etailers). Código funcional en `main`; queda integrar esta rama documental y enviar la entrega. El [README](README.md) es el enunciado; [DATA_RULES](DATA_RULES.md) contiene las reglas detalladas y [TECH_SPEC](TECH_SPEC.md) la arquitectura.

## Cómo levantar desde cero

Necesita Docker y Python 3.13. Verificado en macOS con Python 3.13.13, Compose 2.38.2 y MySQL 8.0.46.

```bash
git clone https://github.com/polalco13/prueba-tecnica-etailers.git
cd prueba-tecnica-etailers
test -f .env || cp .env.example .env
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
docker compose up -d --wait
curl --fail http://localhost:3001/health
.venv/bin/python -m src.db migrate
MAKE_WEBHOOK_URL= .venv/bin/python -m src.etl
.venv/bin/python -m uvicorn src.web.app:app --host 127.0.0.1 --port 8000
```

Abrir http://127.0.0.1:8000. La primera carga tiene Make desactivado; para conectarlo, seguir [su configuración](make/README.md). La web consulta la publicación existente: no carga fuentes ni envía notificaciones.

Compose levanta MySQL en 3307 y stock en 3001 con credenciales demo del enunciado. Estos valores están escritos en Compose; editar `.env` no cambia automáticamente los servicios. Dependencias fijadas en [requirements.txt](requirements.txt): FastAPI/Jinja2 para HTML, PyMySQL para MySQL y httpx para ambas integraciones HTTP, sin ORM ni SPA. Chart.js se sirve [localmente](src/web/static/vendor/README.md), sin Node ni CDN.

Aplicar siempre las migraciones hasta `004_make_delivery`, también con Make desactivado. El migrador actualiza bases existentes sin borrar datos; `db/init` no actualiza volúmenes previos. Revisar el destino antes de migrar. `Ctrl+C` detiene la web y `docker compose stop` conserva la base.

## Ejecución e idempotencia

```bash
.venv/bin/python -m src.etl
```

Extrae y valida las cuatro fuentes antes de publicar en una transacción InnoDB. Una extracción incompleta o un fallo SQL conserva la publicación anterior; un lock MySQL impide escritores simultáneos. Fallos y rechazos se registran con `run_id`.

SKU único, ID de pedido único y firma de línea permiten repetir la instantánea sin duplicar negocio. Las entidades ausentes se reconcilian; productos referenciados pasan a históricos. Cada ejecución añade auditoría. La firma usa pedido, SKU, cantidad, precio y descuento: sin ID de origen, dos líneas legítimas idénticas son indistinguibles.

Salida: **0** = publicación confirmada y Make desactivado/aceptado por HTTP; **1** = fallo del ETL/configuración; **2** = negocio publicado, entrega no confirmada. Una caída abrupta puede dejar un run `running` para revisión manual. Para recuperar una notificación, reenviar el resumen persistido:

```bash
.venv/bin/python -m src.etl --resend-make RUN_ID
```

Un run ya aceptado no repite HTTP salvo `--force`; revisar antes el historial de Make.

## Esquema de base de datos

| Tabla | Finalidad y relaciones |
| --- | --- |
| `products` | SKU único, coste neto, PVP, categoría y stock; comercial o histórico. |
| `stock_by_warehouse` | Una observación por producto/almacén, FK a producto; cantidad, reservas y fecha. |
| `orders` | Cabecera única por ID de origen: fecha, canal, estado y marca de parcial. |
| `order_lines` | FK a pedido y producto, firma única; cantidad, precio y descuento. |
| `etl_runs` | Estado, hashes, contadores y resumen persistido de Make por ejecución. |
| `rejections` | FK a ejecución; fuente, localizador, entidad, acción y motivo. |

`orders → order_lines → products` mantiene FKs reales sin perder ventas de SKUs ausentes: se crean históricos mínimos con coste/PVP/stock `NULL`. `UNIQUE`, `CHECK` y FKs complementan la validación Python. Dinero usa `Decimal`/`DECIMAL`; las [migraciones](db/migrations/) están versionadas.

## Decisiones sobre datos y descartes

| Caso | Criterio aplicado |
| --- | --- |
| Codificaciones/columnas | Catálogo Latin-1 con `;`, pedidos UTF-8 BOM con `,`, XML UTF-8; lectores respetan comillas. Columnas incorrectas rechazan fila; archivo ilegible falla ejecución. |
| Vacíos/números | Centinelas completos → `NULL`. Coma/punto y miles inequívocos se normalizan; dinero ambiguo se rechaza. No se inventan campos obligatorios. |
| Campos opcionales | EAN inválido/científico, peso/IVA/alta inválidos → campo `NULL` con incidencia, conservando el producto cuando es válido. No se reconstruyen códigos. |
| SKU repetido | Duplicado exacto → una ocurrencia; valores contradictorios → primera fila válida en orden del CSV, resto auditado. No hay fecha de actualización para elegir la última. |
| Precio neto | Excepción XML manda; si no, `coste × (1 − descuento categoría − descuento marca)`. Descuentos aditivos; tarifas generales contradictorias abortan. Volumen/portes no se aplican sin datos de compra. |
| Cabeceras | Fechas estrictas; vacíos solo heredan un valor inequívoco del mismo pedido. Cliente compara mayúsculas sin unir nombres por similitud. Estados/canales se canonizan; conflictos reales rechazan el pedido. |
| Líneas | `10%`, `10` y `0,1` → 10 %; `1` sin símbolo → 1 %. Cantidad cero/fraccionaria se rechaza; negativa solo en DEVUELTO. Duplicados por firma; líneas válidas de parciales se conservan. |
| Stock | Paginación completa y reintentos acotados ante 500/429/timeout. Suma física de `quantity`; `reserved` separado. Ausencia/total inválido → `NULL`, nunca cero. SKU ajeno al catálogo se rechaza. |

La auditoría diferencia rechazo, deduplicación, campo descartado y aviso. Por fuente: `leídas = aceptadas + rechazadas + deduplicadas`. Una fila cuenta una vez como rechazada aunque tenga varios motivos. Reglas completas: [DATA_RULES](DATA_RULES.md); decisiones de carga/históricos: [ADR](docs/adr/README.md).

## Facturación, margen y panel

Facturación operativa: pedidos **ENVIADO/COMPLETADO**, líneas válidas positivas, desde 01/04/2025 hasta la fecha analítica. Cada línea se redondea a dos decimales con `ROUND_HALF_UP` antes de sumar; ticket = facturación / pedidos elegibles. Un parcial aporta sus líneas válidas. Pendientes, cancelados y devueltos quedan fuera; las devoluciones se conservan sin compensar una venta no vinculada.

El margen resta el coste neto **actual** de líneas con coste conocido. Muestra ventas sin coste y cobertura, sin tratarlas como coste cero. Es estimación, no rentabilidad histórica exacta: moneda/IVA y comparabilidad ERP/proveedor siguen sin confirmar.

El margen negativo observado tiene una causa visible en las fuentes: costes contradictorios de PRV-2013, PRV-2061 y PRV-2104, conservados según la primera fila válida. Por ejemplo, PRV-2013 presenta 34.400,16 frente a 318,52. Se muestra un aviso; no se corrige el origen para obtener un margen positivo.

El panel incluye evolución mensual de facturación/unidades, KPIs, canales, categorías, top 10, margen/cobertura y bajo mínimos. Completa meses vacíos y señala el actual como parcial; tiene tabla exacta sin JavaScript. Bajo mínimos usa stock físico conocido <5 y ventas elegibles desde la fecha analítica menos tres meses hasta esa fecha, ambos días incluidos. El catálogo comercial tiene búsqueda, categoría y paginación; sus filtros no cambian las estadísticas.

## Make

El resumen `etl-summary-v1` se guarda al publicar y se envía después del commit. Make valida versión/estado/ID y ejecuta histórico primero:

- Google Sheets: una fila por `run_id`, también sin alerta.
- Gmail: alerta si `rows_rejected > MAKE_REJECTION_THRESHOLD` o hay bajo stock; después marca `email_sent_at`.

Umbral inicial 0; duplicados/avisos no cuentan como rechazados. Incluye motivos, facturación del mes anterior y bajo stock, sin clientes ni filas completas. Los fallos completos quedan en auditoría local y no generan resumen de éxito.

[Blueprint](make/escenario.blueprint.json), [configuración/importación](make/README.md) y [ejecución real](make/capturas/f10-real-etl-destinations.png). HTTP 2xx confirma recepción, no destinos. Se observó bloqueo del reenvío; Gmail puede repetirse si envía y falla la marca. Recuperación externa y ejecución de la copia importada no verificadas.

## Verificación realizada

El 28/09/2026, desde clon nuevo de `main` (`aab89b9`) y MySQL aislado, dos cargas originales dejaron idénticos valores de negocio, con FKs y contadores correctos. Make desactivado en esa comprobación.

| Fuente | Leídas | Aceptadas | Rechazadas | Deduplicadas |
| --- | ---: | ---: | ---: | ---: |
| Catálogo | 133 | 115 | 15 | 3 |
| Stock | 230 | 206 | 24 | 0 |
| Pedidos | 1.142 | 1.101 | 33 | 8 |

**115 comerciales + 44 históricos, 358 pedidos y 1.101 líneas**; 30 pedidos parciales. De 359 IDs originales, `PED-2025-00122` no entra por fecha ausente (fila 390, `MISSING_ORDER_DATE`).

A 28/09/2026: facturación **1.381.450,43**, **269 pedidos elegibles**, ticket **5.135,50**, margen conocido **−2.954.287,69**, cobertura **90,36 %** y **12 bajo mínimos**. Recálculo independiente coincidente con SQL; no hay fuente contable para reconciliar importes fiscales.

**397 tests aprobados** (347 sin BD y 50 MySQL), Ruff/formato correctos; navegador con gráfico, filtros y paginación verificados. Permanece deprecación Starlette/TestClient. Make acreditado aparte el 27/09/2026: histórico, correo recibido y marca contrastados para un ETL real; [detalle](make/README.md#cierre-y-límites-de-verificación).

[Reporte de repetibilidad](docs/evidence/f12/repeatability.json) · [Procedimiento aislado](docs/validation/README.md) · [Dos capturas de entrega](docs/evidence/README.md).

### Cómo ejecutar tests

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests docs/validation
.venv/bin/ruff format --check src tests docs/validation
```

Sin `F4_TEST_DB_PORT` se omiten las 50 pruebas MySQL. La [guía aislada](docs/validation/README.md) prepara otra base y ejecuta todas; no usar `catalogo` ni correr pytest junto al ETL en la misma instancia.

### Comprobar un registro

Catálogo fila 98, PRV-2002: `65.83 × (1 − 0.10 − 0.08) = 53.9806`, igual a MySQL. PRV-2001 usa excepción `165.7500`, sin descuentos adicionales. Para localizar descartes sin exponer clientes:

```sql
SELECT source, record_locator, entity_key, reason_code, action
FROM rejections
WHERE run_id = (
    SELECT id FROM etl_runs WHERE status = 'completed'
    ORDER BY finished_at DESC LIMIT 1
) AND entity_key IN ('PED-2025-00122', 'PRV-9001');
```

Una columna de pedidos se cambia en `src/etl/orders.py`, contratos/persistencia y migración si procede; la paginación en `src/etl/stock_client.py`; desgloses en `src/analytics/queries.py` y presentación web. Actualizar reglas y regresiones cuando cambien contratos.

## Qué cambiaría con cinco millones de líneas

El primer límite previsible es memoria: hoy se materializa la instantánea para validar pedidos y duplicados. Pasaría a streaming y staging por lotes con índices para resolver firmas/cabeceras entre lotes. Publicaría solo tras validar la instantánea completa, manteniendo atomicidad; mediría locks/escrituras. Revisaría índices y planes SQL y precalcularía agregados si las latencias lo justifican.

Mediría tiempo, pico de memoria y filas/s con una réplica representativa. No hay benchmark de cinco millones ni SLA prometido. Incremental necesita contrato de cambios/bajas e ID estable de línea; `updated_since` de stock por sí solo no detecta bajas.

## Qué quedó fuera y entrega

Fuera por tiempo: incremental, contenedor de la aplicación Python y comparativa interanual. Sí hay reintentos, logs, tests y auditoría. No se deducen costes históricos, vínculos de devolución ni disponibilidad descontando reservas; el timestamp más reciente tampoco garantiza frescura común de almacenes.

Se utilizó Codex para implementación y verificación; el autor confirmó decisiones y configuró/ejecutó los destinos externos. Las pruebas HTTP simuladas no se presentan como ejecuciones de Make.

El historial conserva seis ramas/PR integradas en `main`, superando tres ramas y dos PR exigidas. **Pendiente:** integrar `feature/delivery-docs` y enviar el correo de entrega con las dos capturas requeridas.
