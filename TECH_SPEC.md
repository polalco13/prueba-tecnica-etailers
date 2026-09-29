# Arquitectura de la solución

Estado del código y validación: [SOLUCION](SOLUCION.md). Requisitos: [README](README.md). Reglas de negocio: [DATA_RULES](DATA_RULES.md). Las decisiones de carga, históricos, dinero y Make están en [ADR](docs/adr/README.md).

## Flujo y tecnologías

```text
CSV catálogo + XML tarifas + CSV pedidos + REST stock
        → extracción → normalización/validación → lote
        → transacción MySQL → consultas → FastAPI/Jinja2 + Chart.js
                             → resumen persistido → commit → Make
```

Un proyecto Python 3.13, un comando ETL síncrono y una web de lectura. Se validan todas las fuentes antes de abrir la transacción de negocio. Los rechazos recuperables se aíslan por fila/campo; una extracción incompleta o un fallo SQL no publica un estado parcial. Un advisory lock MySQL permite un solo escritor por servidor.

Dependencias fijadas en [requirements.txt](requirements.txt): PyMySQL para SQL visible y parametrizado, httpx para stock/webhook, FastAPI/Uvicorn/Jinja2 para HTML y pytest para pruebas. `csv`, ElementTree, Decimal, datetime y logging son de la biblioteca estándar. Sin ORM, SPA ni proceso npm. Chart.js 4.5.1 se sirve localmente con [procedencia y licencia](src/web/static/vendor/README.md). No se añadieron dependencias en la corrección final.

## Responsabilidades

| Código | Responsabilidad |
| --- | --- |
| `src/config.py`, `src/db.py` | Entorno validado, logs, conexión y migraciones. |
| `src/etl/catalog.py`, `normalize.py`, `pricing.py` | Lectura con procedencia, reglas puras y coste neto. El sufijo `?` se trata exclusivamente en el catálogo. |
| `stock_client.py`, `stock.py`, `orders.py` | Paginación/reintentos, consolidación y cabeceras/líneas. |
| `runner.py`, `repository.py`, `records.py` | Ciclo de ejecución, publicación/reconciliación y contratos tipados. |
| `reporting.py`, `make_client.py` | Contadores, resumen congelado y entrega posterior al commit. |
| `src/analytics/` | Definición única de métricas y catálogo mediante SQL. |
| `src/web/` | Filtros, HTML y recursos locales; no recalcula dinero en JavaScript. |

## Modelo y publicación

Las [migraciones 001–004](db/migrations/) crean tablas InnoDB/utf8mb4. Aplicarlas mediante `python -m src.db migrate`; `db/init` no modifica volúmenes existentes.

| Tabla | Integridad |
| --- | --- |
| `products` | SKU único, FK al run, coste/PVP `DECIMAL(18,4)`, ratios `DECIMAL(9,6)`, flags comercial/histórico y stock nullable con estado coherente. Índice categoría/SKU. |
| `orders` | ID de origen único, fecha, estado/canal y marca de parcial. Índice estado/fecha. |
| `order_lines` | FK no nula a pedido/producto/run; firma única por pedido, cantidad BIGINT firmada y localizador. Índice producto/pedido. |
| `stock_by_warehouse` | PK producto/almacén y FKs; cantidades, reserva y fecha UTC. |
| `etl_runs` | Estado, hashes, versión de reglas, contadores y metadatos/resumen Make. |
| `rejections` | FK al run; fuente/localizador/motivo/campo únicos por ejecución, acción, severidad y extracto limitado. No FK a una entidad que puede no existir. |

FKs, UNIQUE y CHECKs cubren relaciones, dominios y rangos locales. Las reglas entre fuentes/candidatos se validan antes de cargar. No se desactivan FKs. Consultas y valores de origen están parametrizados; no interpolar filtros web en SQL.

La transacción hace upsert por claves naturales, sincroniza líneas/almacenes y retira líneas/pedidos ausentes del conjunto aceptado. Productos ausentes se conservan como históricos con atributos actuales desconocidos. No usa TRUNCATE. Un CSV vacío o sin entidades válidas aborta antes de reconciliar. Cada intento tiene auditoría durable; los runs completados se confirman junto con el negocio, los fallos aparte. Detalles y limitaciones de identidad en ADR 002/003.

## Stock y HTTP

API autenticada: `data` y `meta` con página, tamaño, totales y `has_next`. Verificar avance, tamaño exacto y totales constantes; completar todas las páginas. Hash de stock sobre respuestas 200 completas en orden de página, no independiente de la paginación.

Configuración implementada: `STOCK_PER_PAGE=50` (1–100), `STOCK_ATTEMPTS=5` (1–10), timeouts conexión/lectura 5/15 s (1–120), `STOCK_REQUESTS_PER_MINUTE=30` (1–40), `STOCK_BUDGET_SECONDS=300` (1–3600). Reintentar 500 y errores transitorios; 401/403 y otros 4xx no recuperables fallan. Backoff exponencial desde 1 s, jitter 0–1 y tope 30; 429 respeta Retry-After en segundos o HTTP-date, aunque exceda ese tope, sin exceder presupuesto. El presupuesto incluye descarga/esperas; los timeouts son por operación de red, no una interrupción exacta del proceso. Sin redirects ni proxies del entorno.

No se usa `updated_since`: su filtro inclusivo y ausencia de bajas exigirían watermark, solapamiento y refrescos completos. No se incorporó incremental en esta fase.

## Web y configuración

GET `/` combina búsqueda literal por SKU/nombre/descripción, categoría normalizada y paginación estable por SKU de 20 filas. Los filtros solo afectan al catálogo; página excesiva se ajusta a la última. Entradas malformadas → 422; configuración/BD/esquema no disponibles → 503 saneado. Autoescape HTML. Catálogo, métricas y última publicación se leen en la misma conexión.

Gráfico mixto con ejes separados y tabla mensual HTML, utilizable sin JavaScript. Cobertura, históricos, pedidos parciales, stock desconocido/invalidado y límites fiscales visibles. Chart.js convierte cifras ya calculadas para dibujar; los KPIs conservan Decimal/texto. Solo uso local, sin autenticación multiusuario ni exposición pública.

La configuración llega por entorno, con `.env` local sin sobrescribir variables externas. DB_HOST/PORT/NAME/USER/PASSWORD, CSV_PATH/XML_PATH/ORDERS_CSV_PATH, STOCK_API_URL/TOKEN, BUSINESS_TIMEZONE y LOG_LEVEL. Zona por defecto Europe/Madrid; fecha analítica inyectable en Python para tests. Compose contiene credenciales demo literales: editar `.env` no cambia sus servicios. No leer/imprimir secretos en verificaciones documentales.

Make usa MAKE_WEBHOOK_URL vacía para desactivar, MAKE_TIMEOUT=10 (1–60 s) y MAKE_REJECTION_THRESHOLD=0. Resumen y estado de entrega se persisten en la migración 004. Salidas 0/1/2 separan éxito, fallo ETL y negocio publicado sin entrega confirmada. La [guía Make](make/README.md) explica configuración, reenvío y límites externos; HTTP 2xx acredita recepción, no destinos.
