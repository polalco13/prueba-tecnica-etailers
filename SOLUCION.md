# Solución — documento vivo

**Estado: F0–F7 integradas en `main`; F8 analítica SQL implementada y verificada en `feature/dashboard`. Dashboard F9 y Make F10 pendientes.** `TBD` significa pendiente de implementación/verificación; no sustituirlo por estimaciones presentadas como hechos.

Diseño propuesto: [PRD](PRD.md), [TECH_SPEC](TECH_SPEC.md), [DATA_RULES](DATA_RULES.md), [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md), [ADR](docs/adr/README.md). Al finalizar, actualizar esta guía a lo realmente implementado y distinguirlo de propuestas descartadas.

## Resumen

- Problema: consolidar catálogo CSV, tarifas XML, pedidos CSV y stock REST del distribuidor B2B.
- Funcionalidad realmente implementada: bootstrap de dependencias y comprobación local de servicios (F0); configuración, contratos y normalizadores puros (F1); lector/validador del CSV de catálogo (F2); reglas XML y coste neto (F3); persistencia MySQL y auditoría (F4); API paginada y stock por almacén (F5); pedidos, históricos y reconciliación de las cuatro fuentes (F6); validación end-to-end con pruebas sintéticas y dos cargas reales repetibles en MySQL aislado (F7); consultas analíticas probadas y contrastadas con una carga real aislada (F8).
- Versión/commit entregado y enlace GitHub: **TBD**.
- A01–A05: verificados técnicamente en F7. SQL de A07 y A08: verificado en F8, con supuestos comerciales explícitos más abajo. Interfaz de A06–A07, Make y extras: pendientes de sus fases; no se declara el ejercicio completo.

## Arquitectura final

El incremento implementado es CSV/XML/API de stock/CSV de pedidos → lectores y reglas Python → transacción InnoDB MySQL 8 (`products`, `stock_by_warehouse`, `orders`, `order_lines`, `etl_runs`, `rejections`) → consultas SQL de solo lectura en `src/analytics/queries.py`. Las incidencias de fallos se confirman por separado tras rollback; un advisory lock serializa escritores. Diagrama final con web y Make: **TBD**.

## Requisitos de entorno

- Entorno local comprobado en F0 (23/09/2026): Python 3.13.13, Docker 29.2.1 y Compose 2.38.2. MySQL respondió como 8.0.46. Se usa 3.13 porque la versión 3.12 propuesta no está disponible en este equipo; compatibilidad con otros Python **TBD**.
- Dependencias resueltas y fijadas en `requirements.txt`; configuración de pytest y Ruff en `pyproject.toml`. La justificación de dependencias está más abajo. Instalación en otro equipo **TBD**.
- Puertos/servicios del entorno provisto: MySQL host 3307 y API stock 3001; ambos estaban `healthy` en F0. Esta observación local no sustituye la comprobación desde cero de F12.
- Make y los dos destinos: no hay `MAKE_WEBHOOK_URL` ni destinatario de alerta en `.env` local; acceso/conexiones reales **TBD** para F10. El token local se usó en memoria para la comprobación autenticada; no se mostró ni publicó.
- GitHub: `origin` está configurado y un `git push --dry-run` a `feature/etl-products` terminó correctamente; no se publicó esa rama por esta comprobación. La accesibilidad final del repositorio entregado se verificará en F12.
- Zona horaria propuesta en F1: `Europe/Madrid` por defecto, configurable mediante `BUSINESS_TIMEZONE` y pendiente de confirmación comercial. Moneda y base fiscal: **TBD**.

## Cómo levantar desde cero

Pasos de bootstrap comprobados en F0, que F12 debe repetir desde un clon limpio:

1. Clonar repositorio y seleccionar versión de entrega: URL/commit **TBD**.
2. Preparar `.env` a partir de `.env.example` solo si no existe. En F0 ya existía y se conservó. Mantenerlo local; no mostrar claves reales en ejemplos. F1 acepta opcionalmente `ORDERS_CSV_PATH` (por defecto `data/pedidos_historico.csv`), `BUSINESS_TIMEZONE` (por defecto `Europe/Madrid`) y `LOG_LEVEL` (por defecto `INFO`). Variables de fases posteriores: **TBD**.
3. Comprobar que variables de la aplicación coinciden con servicios: Compose tiene valores demo literales y no interpola automáticamente todo `.env`. La conexión local de F0 confirmó que los valores actuales coinciden.
4. El README proporciona `docker compose up -d` para MySQL/API. Después, comprobar `docker compose ps` y `curl --fail http://localhost:3001/health`. En F0 los servicios ya estaban en marcha: se comprobó `docker compose ps`, `/health` y una página autenticada, sin reiniciarlos ni imprimir el token. Se observó `/health` 200, 401 sin token y 200 con token (`data`: 5 elementos, `meta`: `page`, `per_page`, `total_records`, `total_pages`, `has_next`). El token se leyó desde `.env` mediante `python-dotenv` en memoria, no se pasó como literal de línea de comandos.
5. Crear el entorno Python e instalar dependencias fijadas:

   ```bash
   python3.13 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   .venv/bin/python -m pip check
   ```

   En F0 se creó `.venv` local y se instalaron las versiones fijadas. La verificación de instalación desde `requirements.txt` y `pip check` consta en las pruebas realizadas. `.venv` y las cachés de herramientas están ignoradas por Git.
6. Aplicar las migraciones F4–F6 con `.venv/bin/python -m src.db migrate` una vez que `.env` apunte al MySQL deseado. Es idempotente y registra `001_products_and_runs`, `002_stock` y `003_orders` en `schema_migrations`; repetir el comando informa «ya aplicadas». También sirve para un volumen existente sin borrar el volumen: `db/init` solo se ejecuta al inicializarlo. Antes de cualquier migración sobre una BD con datos propios, respaldarla y revisar si ya existen tablas con los mismos nombres. La actualización de esquemas F4/F5 conservó productos e IDs en una base temporal; F6 verificó la reanudación de su migración sin perder pedidos.
7. Arrancar web: comando, host/puerto y URL local **TBD**.
8. Registrar validación desde clon/BD de pruebas nuevos, fecha y commit: **TBD**. No ejecutar pruebas destructivas sobre el volumen del usuario.

El incremento F6 permite cargar las cuatro fuentes y F7 lo verificó en MySQL aislado; todavía no hay web ni Make. En F12 habrá que repetir el procedimiento desde un clon limpio.

### Dependencias elegidas en F0

`PyMySQL` proporciona el driver de MySQL que falta en la biblioteca estándar; `httpx` sirve tanto para la API como para el webhook y permite simular transporte en tests. `FastAPI`, `Uvicorn` y `Jinja2` sostendrán la página HTML propuesta, sin SPA ni ORM. `python-dotenv` permite cargar `.env` local sin ejecutarlo como shell ni sobrescribir variables; `pytest` verifica reglas futuras y `Ruff` configura un lint ligero. No se añade pandas, un segundo cliente HTTP ni un framework de migraciones. El uso de estas dependencias por módulos de aplicación queda pendiente de sus fases; F0 solo valida instalación/importación.

## Cómo ejecutar el ETL

- **Comando F6:** `.venv/bin/python -m src.etl` después de aplicar las migraciones. Usa también `ORDERS_CSV_PATH` (por defecto `data/pedidos_historico.csv`). Extrae las cuatro fuentes antes de abrir la transacción de negocio y publica pedidos, líneas e históricos junto con catálogo y stock. No envía Make.
- Código de salida `0`: publicación confirmada; puede haber filas rechazadas y quedan en `rejections`. Código `1`: fallo o concurrencia, sin publicar un catálogo parcial. Revisar `etl_runs` y las incidencias del `run_id` del log para fallos ocurridos tras crear el run. La caída antes de obtener el lock o antes de crear el run no genera auditoría de ejecución.
- Repetir el mismo comando con los mismos CSV/XML y respuestas completas de stock mantiene los valores de negocio y añade un `etl_runs`/sus incidencias nuevos. Los SKU que faltan en una instantánea válida pasan a históricos, con precios y stock `NULL`; un catálogo vacío o sin productos válidos, o un fichero modificado durante la extracción, falla y conserva la versión anterior. Solo se admite un escritor mediante advisory lock MySQL. Una caída abrupta puede dejar un run `running` para revisión manual.
- Parámetros opcionales de stock: `STOCK_PER_PAGE=50`, `STOCK_ATTEMPTS=5`, `STOCK_CONNECT_TIMEOUT=5`, `STOCK_READ_TIMEOUT=15`, `STOCK_REQUESTS_PER_MINUTE=30`, `STOCK_BUDGET_SECONDS=300`. Tiempos en segundos; límites y reintentos en [TECH_SPEC](TECH_SPEC.md#api-de-stock). No hace falta modificar `.env` para usar estos valores. Dashboard y notificación: **TBD**.
- Reenvío a Make de un run confirmado sin repetir ETL: **TBD**.
- Recuperación automática adicional: **TBD**.

### Comprobación manual en la base del usuario (pendiente)

Las comprobaciones F6/F7 se hicieron en MySQL temporal; esta tarea no migró ni recargó la base `catalogo` del usuario. Para llevar este incremento a esa base, con los servicios activos y `.env` apuntando a ella:

```bash
.venv/bin/python -m src.db migrate
.venv/bin/python -m src.etl
```

Después, refrescar tablas en DBeaver. Deben aparecer `stock_by_warehouse`, `orders` y `order_lines`. Estas consultas permiten contrastar el último run y los totales; con las mismas fuentes se esperan los contadores de filas de la tabla de evidencias. El número de históricos creados depende de los que ya existieran en esa base:

```sql
SELECT id, status, phase, error_code, counters
FROM etl_runs ORDER BY started_at DESC LIMIT 1;

SELECT stock_status, COUNT(*) AS productos
FROM products WHERE in_catalog = 1 GROUP BY stock_status;

SELECT p.sku, p.stock_total, SUM(s.quantity) AS suma_almacenes,
       SUM(s.reserved) AS reservado
FROM products p JOIN stock_by_warehouse s ON s.product_id = p.id
WHERE p.stock_status = 'known'
GROUP BY p.id, p.sku, p.stock_total
HAVING p.stock_total <> SUM(s.quantity);
```

La última consulta debe devolver cero filas. Las reservas permanecen aparte: no se restan de `stock_total`. Para revisar pedidos:

```sql
SELECT source_order_id, status, has_rejected_lines, COUNT(l.id) AS lineas
FROM orders o LEFT JOIN order_lines l ON l.order_id = o.id
GROUP BY o.id, source_order_id, status, has_rejected_lines
ORDER BY source_order_id;
```

La comprobación visual en la base del usuario es opcional para revisar el resultado local; no sustituye las pruebas MySQL de F7–F8 ya ejecutadas. PR 3 de F6–F7 está integrada en `main`. F8 no modifica el esquema ni requiere recargar datos del usuario; si su base ya contiene F6, puede ejecutar las consultas de lectura con la misma definición de fecha.

## Cómo ejecutar tests

Las pruebas unitarias se ejecutan sin BD ni API real; las pruebas de integración F4–F8 requieren un MySQL 8 separado:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
```

Sin `F4_TEST_DB_PORT`, los tests de integración se omiten. Para incluirlos, arrancar un contenedor temporal MySQL 8 **sin montar `mysql_data`**, con una base cuyo nombre empiece por `f4_test_`; pasar `F4_TEST_DB_PORT` y `F4_TEST_DB_PASSWORD` al proceso de pytest. Son opcionales `F4_TEST_DB_HOST` (127.0.0.1), `F4_TEST_DB_NAME` (`f4_test_catalog`) y `F4_TEST_DB_USER` (`f4_tester`). El test aplica la migración en esa base y crea solo datos sintéticos. No apuntarlo al volumen o base `catalogo` del usuario. Se conservan los nombres `F4_TEST_*` para todas las fases. Tras F8 hay **339 tests** (307 sin BD y 32 de integración): F8 añade seis casos SQL sintéticos; la regresión F0–F7 conserva sus 333. Sin BD se omiten los 32 de integración, por lo que esa ejecución sola no acredita F7 ni F8.

Para repetir solo F7, con las variables anteriores configuradas:

```bash
.venv/bin/python -m pytest tests/integration/test_etl.py -q
```

Las fixtures se generan en directorios temporales: CSV Latin-1, XML, pedidos UTF-8 BOM y HTTP simulado con fechas fijas. Las cinco pruebas comprueban carga/repetición/trazas, duplicados sin rechazos, fallo de última página, fallo MySQL al publicar y exclusión de un segundo escritor mientras el primero extrae. Las consultas de [etl_checks.py](tests/integration/etl_checks.py) verifican todas las FKs, claves únicas, líneas negativas según estado, históricos sin coste, sumas de stock y contadores contra incidencias persistidas. Los tests previos siguen comprobando las restricciones con escrituras inválidas y la corrección/retirada de líneas.

## Esquema de base de datos

F4 aplicó [`001_products_and_runs.sql`](db/migrations/001_products_and_runs.sql) en MySQL 8 aislado: `etl_runs` (PK UUID), `products` (PK numérica, SKU binario único y FK a run) y `rejections` (FK a run, UNIQUE por ejecución/fuente/localizador/motivo/campo). `DECIMAL` conserva precios y ratios; los `CHECK` controlan precios positivos, rangos, estado histórico y stock desconocido. La migración se registra en `schema_migrations`. Se verificaron `UNIQUE`, FK y `CHECK` con inserciones/actualizaciones inválidas en MySQL. F5 añade [`002_stock.sql`](db/migrations/002_stock.sql): `stock_by_warehouse` con PK producto/almacén, FK a producto/run y CHECK de cantidades y reservas no negativas; añade también `etl_runs.stock_sha256`. F6 añade [`003_orders.sql`](db/migrations/003_orders.sql): `orders` y `order_lines` con FKs, UNIQUE de pedido y firma de línea, CHECKs de dominios y `etl_runs.orders_sha256`. Los históricos mínimos mantienen la FK sin inventar atributos.

## Decisiones sobre calidad de datos

Reglas en [DATA_RULES](DATA_RULES.md): encoding por fuente, nulos, precios Decimal, EAN conservador, selección determinista de duplicados, descuentos, fechas, estados/canales y stock desconocido. F1 implantó normalizadores puros; un descuento sin `%` igual a `1` se interpreta como 1 %. F2 lee el catálogo Latin-1 con `csv`, rechaza campos obligatorios inválidos y descarta solo opcionales incorrectos; conserva coste CSV inválido condicionado a una excepción. F3 resuelve tarifas y escoge la primera fila válida por SKU; conflictos de tarifa general abortan. F4 persiste con auditoría. F5 integra stock, separando versiones/duplicados de rechazos y reservas del físico. F6 leyó 1.142 filas reales de pedidos: 786 aceptadas, 349 rechazadas y 7 deduplicadas, con 277 pedidos, 22 parciales y 36 SKUs históricos potenciales. F7 confirmó inicialmente esas cifras con v1. El usuario resolvió después la incongruencia de capitalización (ADR 004); con v2 se publican 1.101 líneas y 358 pedidos, como se detalla abajo.

La lectura aislada del catálogo original en F2 (sin tarifas ni MySQL) observó **133 registros de origen, 130 candidatos antes de precio final, 10 con coste CSV pendiente de validar por excepción y 13 incidencias preliminares**: 2 de columnas, 5 de campo obligatorio y 6 de EAN. Varios motivos pueden pertenecer a una sola fila. Eran cifras provisionales, antes de la selección económica de F3. Los ficheros de `data/` no se modificaron.

F3 cruza ese catálogo con el XML real. El parser reconoció 6 reglas de categoría, 10 de marca y 14 excepciones; registró 5 términos de volumen/condiciones no aplicados. El resultado seleccionó 115 productos con coste neto calculado (103 desde coste CSV y descuentos, 12 por excepción). Las 133 filas se reconcilian como **115 aceptadas + 15 rechazadas + 3 deduplicadas**. Hay 19 incidencias de acción «rechazar» porque una fila puede tener varios motivos; además hay 7 campos descartados y 7 avisos, incluidos 2 por excepciones sin candidato. F4 confirmó estas cifras con CSV/XML originales en una BD temporal: 115 productos vigentes y 36 incidencias persistidas por run. No es una ejecución de las cuatro fuentes. EUR y base fiscal comparable siguen sin confirmar.

## Definición de facturación y margen

F8 implementa la **facturación operativa** propuesta: pedidos `ENVIADO`/`COMPLETADO`, líneas válidas con cantidad positiva y fecha entre 2025-04-01 y `as_of`, ambos incluidos. Cancelados, pendientes y devueltos quedan fuera. Las devoluciones permanecen en la BD pero no se compensan sin vínculo con la venta original. Un pedido con líneas rechazadas cuenta una vez si tiene al menos una línea válida elegible; solo esas líneas aportan importe. Cada línea se calcula como `ROUND_HALF_UP(cantidad × precio_unitario × (1 − descuento), 2)` antes de sumar. El ticket es facturación / pedidos, a dos decimales, o `NULL` si no hay pedidos.

`as_of` por defecto es el día actual de `BUSINESS_TIMEZONE` (`Europe/Madrid` por defecto); para repetir medidas se pasa una fecha fija. La serie completa los meses desde abril de 2025 con cero y marca el mes de `as_of` como parcial. El mes anterior de Make es el mes natural completo inmediatamente previo a `as_of`, sujeto al mismo límite global desde abril de 2025. Categorías con distinta capitalización se agrupan por `category_key` del ETL; las históricas sin categoría forman el grupo explícito `Sin categoría`. Canal, categoría y margen parten del mismo conjunto de líneas; no se multiplica por almacenes.

El margen conocido suma, por línea con `net_cost` actual no nulo, el importe menos `ROUND_HALF_UP(cantidad × net_cost, 2)`. Puede ser negativo. Se muestran por separado ventas con y sin coste y la cobertura como fracción de ventas con coste conocido sobre ventas totales, a cuatro decimales (`NULL` si el total es cero). Es una **estimación a coste actual**, no rentabilidad histórica exacta. Moneda EUR, IVA y comparabilidad del precio ERP con el coste proveedor: **pendientes de confirmación comercial**. Hasta entonces no presentar estas cifras como facturación fiscal o beneficio definitivo.

## Productos históricos

F4 conserva el ID de un producto que desaparece del CSV, lo marca histórico y limpia atributos comerciales, coste y stock. F6 crea/reutiliza el mismo ID para un SKU de pedido sin producto comercial, con atributos desconocidos a `NULL`; si reaparece en catálogo, lo promociona. Estas transiciones, FKs y retirada de pedidos pasaron contra MySQL con fixtures sintéticas. F8 incluye las ventas históricas y separa sus importes del margen con coste conocido; la carga real a 2026-09-25 tiene cobertura monetaria de `0.9036`.

## Idempotencia

F4 usa clave única SKU, upsert y reconciliación de catálogo completo con auditoría por run. F6 usa la firma `order-line-v1` y una instantánea completa de pedidos; las firmas idénticas se deduplican y las líneas/pedidos ausentes se retiran. El usuario confirma que el archivo es el entregado para la prueba: se usa entero como dataset del ejercicio, sin afirmar que futuras exportaciones del ERP tengan ese contrato. Se mantiene la deduplicación conforme a ADR 002; las ocho repeticiones aceptables del archivo coinciden en sus nueve columnas. Sin ID de línea no se pueden distinguir eventuales líneas legítimas idénticas.

F6 verificó en MySQL sintético la corrección de una línea, retirada de pedidos ausentes y promoción/retirada de históricos. La repetición de F7 con reglas v2 comparó las cuatro tablas completas tras dos cargas reales: mismos valores, IDs y cantidades de filas. Solo se excluyó `last_run_id`; fechas de origen, firmas y localizadores de línea se conservaron en la comparación. Se añadió un run y su auditoría por carga, con 44 avisos de creación de históricos solo en la primera. Los identificadores, hashes y cifras se detallan abajo.

## Integración Make

- Escenario real, disparador, formato JSON y schema_version: **TBD**.
- Router/filtros, umbral y destinos configurados: **TBD**.
- Código de envío y tratamiento de error/reenvío: **TBD**.
- Blueprint exportado: **TBD**, destino previsto `make/escenario.blueprint.json`.
- Capturas de escenario y ejecución correcta: **TBD**, destino previsto `make/capturas/`.
- run_id real, recepción y confirmación de destinos: **TBD**.
- Política de duplicados y limitaciones de entrega: **TBD**.

No publicar URL secreta del webhook, tokens, identificadores sensibles de conexiones o destinatarios privados en capturas. El correo de alerta se enviará únicamente con destinatario e instrucción de envío autorizados. La evidencia debe proceder del ETL real; una prueba sintética adicional se etiqueta como tal.

## Dashboard

URL local/comando e interfaz: **TBD (F9)**. Las consultas SQL de F8 para KPIs, serie mensual, canales, top 10, categorías, margen/cobertura y bajo stock están implementadas y verificadas; aún no hay página ni gráfico. Captura real sin secretos: **TBD**. Comprobar coherencia visual con SQL y tratamiento visible de NULL/mes actual parcial: **TBD (F9)**.

## Resultados de ejecución

Corrección de F6–F7, 24/09/2026, ADR 004: dos llamadas reales a `run_etl(settings)` con reglas `catalog-stock-orders-v2`, sin sustituir lectores ni HTTP, en `f4_test_orders_v2` inicialmente vacía, sobre MySQL 8.0.46 temporal sin el volumen del usuario. Se aplicaron las tres migraciones; no fue necesaria una migración nueva. La API original entregó cinco páginas de 50 (última de 30); sus respuestas y los ficheros son idénticos a los de la validación anterior. El mock mantiene los registros en memoria. No se usa fecha analítica en F7.

Evidencia anterior conservada: F7 con v1 (`039a403`) produjo 151 productos, 277 pedidos, 786 líneas y 349 filas de pedidos rechazadas; runs `bcef2d47-9487-4707-ac1c-85bfbbfbf00e` / `65fa3677-da9e-418e-bc20-7c6488e99793`, hash de negocio `8b5b29d361941891824dd2cbcdd8edf6471148869dc85c00686a83a610cc4185`. Esos resultados quedan sustituidos por los siguientes tras la confirmación del usuario.

| Evidencia | Resultado real |
| --- | --- |
| Código y reglas | Corrección ADR 004 sobre F6–F7 en `feature/orders`; reglas `catalog-stock-orders-v2`. Solo cambia la equivalencia de cliente de cabecera, sin cambiar la firma de línea. |
| run_id inicial / repetición | `05ad2ff9-1f77-4b9f-84f5-72d228fc4bf1` / `bd8a09fb-b4f2-4df3-8c62-541aef63f4dc`, ambos `completed`. |
| Productos | 159 en ambas cargas: 115 comerciales + 44 históricos. Los históricos sostienen 118 líneas aceptadas: 35 SKUs ausentes del catálogo original y 9 con fila rechazada. |
| Pedidos/líneas | 358 pedidos, 30 parciales y 1.101 líneas en ambas cargas. Los 81 pedidos antes rechazados por capitalización existen y conservan la primera grafía normalizada no vacía, contrastado contra el CSV sin publicar nombres. |
| Stock | 206 observaciones; entre los 115 comerciales, 103 con stock conocido, 12 desconocido y 0 inválido. Cero diferencias frente a SUM(quantity). |
| Integridad | Cero FKs huérfanas en las cuatro tablas y auditoría, cero claves duplicadas, cero pedidos sin líneas. Históricos con coste/PVP/stock NULL. |
| Auditoría | 222 incidencias iniciales y 178 en repetición; la diferencia son 44 creaciones de históricos. Rechazos de origen y deduplicaciones se repiten con el nuevo run_id. |
| Comparación de negocio | Igualdad exacta de las cuatro tablas mediante `business_snapshot`, incluidos IDs y fechas de origen, excluyendo solo `last_run_id`. SHA-256: `f14438e6e9d777f64826857e1ed314793896ededc2f891171690fbf1b15fe0f1` en ambas. |
| Duraciones y API | 9,226 s / 10,941 s, diferencia started_at–finished_at de la auditoría. Primer run sin reintentos; segundo con un reintento en página 4. No es un benchmark. |
| Make / métricas | `make_status=not_applicable`; facturación, ticket, margen y cobertura pendientes de F8; entrega externa pendiente de F10. |

Hashes SHA-256, idénticos antes/después y entre runs:

| Entrada | SHA-256 |
| --- | --- |
| Catálogo CSV | `ebe2a2079d02814b02b3094ef0e9c0d2c696b6a81c21172a8e0a2d2821d9159a` |
| Tarifas XML | `3922610e433d4b6e833a24f7e9db6d6c3c7858fbb8de4694d7fb005af511e3df` |
| Pedidos CSV | `7819b3dc624de1bb6ec7a4dc80e207a5c5a7075c8d6295842aa3fcc7b42e11ac` |
| Stock recibido, hash de páginas guardado en etl_runs | `08987b5f88455dc32034f60c331ed68ebbc94e4d3c33c312ae2f574e51b398bb` |
| Fichero original mock-api/stock.json | `4e0e4f2117766b5a2067d7a055406573afc23f12cb183be7d1944ff5ad72906d` |

| Fuente | Leídas | Aceptadas | Rechazadas | Deduplicadas | Avisos inicial / repetición | Campos descartados |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Catálogo | 133 | 115 | 15 | 3 | 7 / 7 | 7 |
| Stock | 230 | 206 | 24 | 0 | 40 / 40 | 0 |
| Pedidos | 1.142 | 1.101 | 33 | 8 | 80 / 36 | 0 |

En las tres fuentes se cumple `read = accepted + rejected + deduplicated`, contrastado con los localizadores distintos de auditoría y las filas de negocio publicadas. XML tiene reglas, no filas de entidades equivalentes: 6 categorías, 10 marcas y 14 excepciones; sus 7 avisos (5 términos no aplicados y 2 excepciones sin candidato) se incluyen en `catalog_csv.quality_warnings`, conservando `source=tariffs_xml` en auditoría. Esto evita inventar un contador de filas XML comparable al de CSV.

Para reproducir la comparación real, usar otra base temporal inicialmente vacía con las migraciones aplicadas y las cuatro fuentes originales: invocar `run_etl` dos veces, llamar tras cada carga a `assert_integrity`, `assert_counters` y `business_snapshot` de [etl_checks.py](tests/integration/etl_checks.py), comparar los dos snapshots y `snapshot_hash`. Configurar solo la conexión de pruebas por entorno o `dataclasses.replace(load_settings(), ...)`; conservar el token en memoria y no editar `.env`. No ejecutar las fixtures sintéticas sobre esa misma base antes de la medida. El hash de negocio incluye IDs, por lo que demuestra igualdad entre estas cargas, no un identificador universal para bases con historiales distintos.

### Trazas revisadas desde origen hasta MySQL

Contraste directo de las celdas originales, XML/stock y consultas SQL; sin copiar nombres de clientes a evidencias:

| Fuente / localizador | Contraste observado |
| --- | --- |
| Catálogo fila 98, PRV-2002; XML Herramienta manual / Stanley | `65,83` → Decimal 65.83; 10 % + 8 %: `65.83 × (1 − 0.10 − 0.08) = 53.9806`, igual a MySQL. Sin stock observado: NULL. |
| Catálogo fila 66, PRV-2001; excepción XML del mismo SKU | Coste `-0,00` descartado con `NON_POSITIVE_PRICE`; excepción 165.75 → `net_cost=165.7500`, `base_cost=NULL`, origen `exception`. |
| Catálogo filas 5 y 6 | EAN científico de PRV-2075 descartado sin eliminar producto; PRV-9001 rechazado por número de columnas. Auditoría conserva fila y motivo. |
| Stock PRV-2001, page:4/row:38 y page:5/row:5 | MAD-01: quantity 0/reserved 2; BCN-02: 12/0. MySQL publica físico 12 y conserva ambas reservas; aviso para MAD-01. |
| Stock page:1/row:6, PRV-7104 | `UNKNOWN_PRODUCT_SKU`; la observación no crea producto. |
| Pedidos fila 3, PED-2025-00001 / PRV-2104 | `2025-04-19 19:57:00`, `b2c`, `91,75` → día 2025-04-19, B2C, precio 91.7500, cantidad 1, descuento 0. |
| Pedidos fila 2, mismo pedido | Cantidad −3 en COMPLETADO y precio vacío: dos motivos de rechazo, una sola fila rechazada. Se conserva el pedido como parcial por sus líneas válidas. |
| Pedidos fila 14, PED-2025-00004 / PRV-2062 | 50 unidades a 116.03; catálogo fila 38 rechazado por precio no positivo. Se crea histórico con coste NULL y FK válida. Estado CANCELADO conservado; no se calcula facturación en F7. |

Las devoluciones negativas se prueban con fixtures sintéticas. No hay líneas negativas aceptadas en esta carga real: las ocho cantidades negativas originales pertenecen a COMPLETADO/CANCELADO, y se rechazan por cantidad incompatible.

## Resultados analíticos F8

El 25/09/2026 se cargaron las cuatro fuentes originales **una vez** en `f4_test_analytics_real`, MySQL 8.0.46 temporal sin volumen del usuario, con `run_id=d670414d-c73d-409d-ab0b-d0a34df20113` en estado `completed`. Se observaron 159 productos (115 comerciales y 44 históricos), 358 pedidos y 1.101 líneas, coherentes con F7. Se fijó `as_of=2026-09-25` para que el resultado sea reproducible; la base temporal de esta comprobación no se presenta como la BD del usuario.

| Métrica operativa F8 | Resultado de esa carga |
| --- | ---: |
| Facturación / pedidos elegibles / ticket medio | 1.381.450,43 / 269 / 5.135,50 |
| Pedidos elegibles parciales | 23 |
| Ventas B2B / B2C / marketplace | 485.666,36 / 391.949,69 / 503.834,38 |
| Margen conocido estimado | −2.954.287,69 |
| Ventas con coste / sin coste / cobertura | 1.248.262,11 / 133.188,32 / 0,9036 |
| Facturación agosto 2026 (mes anterior completo) | 56.696,84 |
| Productos vigentes con stock conocido <5 y ventas desde 2026-06-25 | 12 |
| Meses de la serie abril 2025–septiembre 2026 | 18; septiembre marcado parcial |

Un cálculo independiente en Python leyó las líneas MySQL sin usar el SQL de `AnalyticsQueries` y aplicó `Decimal`/redondeo por línea. Coincidieron exactamente facturación, pedidos/parciales, cada mes y sus unidades, canales, categorías por `category_key`, top 10, margen conocido, importe sin coste, mes anterior y conjunto/unidades de bajo stock. La suma por canal y por categoría es 1.381.450,43 en ambos casos. El top 10 se ordena por facturación descendente y SKU ascendente en empate. En la fila 3 del CSV original, `PRV-2104`, cantidad 1 y precio `91,75`, la BD conserva `91.7500` con descuento cero; aporta 91,75 a abril de 2025. No se copiaron nombres de clientes a la evidencia.

La serie observada pasa de 106.943,03 y 295 unidades en julio de 2025 a 2.682,07 y 11 unidades en agosto; la BD contiene 14 pedidos/41 líneas elegibles en julio y 2 pedidos/5 líneas elegibles en agosto. También hay 2 pedidos cancelados en agosto. El descenso está en el origen aceptado, pero **no se atribuye a estacionalidad ni a una causa comercial** sin confirmación.

El margen negativo está dominado por dos SKU con coste actual muy superior al PVP y al precio de pedido. Para `PRV-2013`, el catálogo original tiene coste `34400,16` en fila 97 y `318.52` en fila 109; conforme a la regla F3 ganó la primera fila válida, el coste neto quedó 28.208,1312 y la segunda se auditó como `CONFLICTING_PRODUCT_SKU`. Su contribución al margen es −3.242.476,26. `PRV-2061` sigue el mismo patrón: costes originales `2532,60` (fila 23) y `23.45` (fila 126), neto elegido 2.254,0140 y contribución −227.755,29. F8 no cambia la deduplicación ni sustituye costes: el origen y la semántica comercial de esos importes requieren revisión antes de interpretar el margen como rentabilidad. EUR/IVA siguen sin confirmarse.

**Decisión pendiente para valorar más adelante:** confirmar con el proveedor qué fila/coste corresponde a cada uno de esos SKU y si coste y precio de pedido son importes unitarios en la misma moneda y base de IVA. Hasta recibir esa información, la propuesta para F9 es presentar el KPI como «margen estimado a coste actual», mostrar cobertura y un aviso visible sobre los dos costes conflictivos y la base fiscal sin confirmar. Esto aún no es una decisión comercial ni una interfaz implementada. Si se confirma un error de origen, habrá que revisar la política de selección de catálogo en F2/F3, versionar la regla y repetir ETL y pruebas; no sustituir por la segunda fila ni excluir ventas del margen silenciosamente.

Para revisar en DBeaver el total a la misma fecha, esta consulta de solo lectura reproduce el filtro y el redondeo de F8; el resto del SQL canónico está en [`queries.py`](src/analytics/queries.py):

```sql
WITH eligible AS (
    SELECT o.id AS order_id,
           ROUND(l.quantity * l.unit_price * (1 - l.discount), 2) AS amount
    FROM orders o JOIN order_lines l ON l.order_id = o.id
    WHERE o.status IN ('ENVIADO', 'COMPLETADO') AND l.quantity > 0
      AND o.order_date BETWEEN '2025-04-01' AND '2026-09-25'
)
SELECT COALESCE(SUM(amount), 0) AS facturacion_operativa,
       COUNT(DISTINCT order_id) AS pedidos_elegibles
FROM eligible;
```

Las seis pruebas sintéticas de [`test_analytics.py`](tests/integration/test_analytics.py) cubren los casos difíciles sin usar ni modificar las fuentes reales: dos almacenes sin doble conteo, redondeo individual de medio céntimo, histórico sin coste, margen negativo, meses vacíos/actual parcial, límites de fecha y mes natural anterior incluso cambio de año, estados excluidos, empate del top 10 y categorías con mayúsculas distintas. La ventana de tres meses ajusta 31 de mayo a 28/29 de febrero y excluye stock `NULL` o igual a 5.

## Rechazos

Consulta de revisión: `SELECT source, record_locator, entity_key, reason_code, field_name, action FROM rejections WHERE run_id = ? ORDER BY id` (sustituir `?` por parámetro del cliente). El nombre `rejections` incluye también deduplicaciones, campos descartados y avisos; no usar COUNT(*) de toda la tabla como contador de filas rechazadas.

| Fuente | Motivos de acción reject_row (incidencias) | Filas distintas |
| --- | --- | ---: |
| Catálogo | AMBIGUOUS_NUMBER 5; CONFLICTING_PRODUCT_SKU 3; INVALID_COLUMN_COUNT 2; MISSING_REQUIRED_FIELD 5; NON_POSITIVE_PRICE 4 | 15 |
| Stock | UNKNOWN_PRODUCT_SKU 24 | 24 |
| Pedidos | INVALID_QUANTITY 9; INVALID_QUANTITY_FOR_STATUS 8; MISSING_ORDER_DATE 1; MISSING_REQUIRED_FIELD 16 | 33 |

Catálogo tiene 19 incidencias de rechazo y pedidos 34, porque una fila puede tener varios motivos. Stock tiene además 28 avisos por reservas y 12 por ausencia. Pedidos tiene 22 avisos de herencia, 14 de descuento vacío y 44 de creación histórica solo en la primera carga. Todas las diferencias de contadores están explicadas.

**Incongruencia de cliente resuelta (ADR 004):** el usuario confirmó que las variantes de mayúsculas/minúsculas representan al mismo cliente. Ahora se comparan con `casefold()` tras NFC/espacios, conservando la primera grafía válida; nombres realmente distintos siguen en conflicto. De las 324 filas antes rechazadas por cabecera, se recuperan 315 líneas, 8 se rechazan por otros errores y 1 se deduplica. Los 81 pedidos se recuperan, con sus líneas válidas. Se mantiene el límite de no unir nombres por similitud ni eliminar tildes.

## Pruebas realizadas

| Verificación | Comando / evidencia | Resultado |
| --- | --- | --- |
| F0: versiones y dependencias | `python3.13 --version`, `docker --version`, `docker compose version`, `pip install -r requirements.txt`, `pip check`, importación de 8 dependencias directas | Python 3.13.13; Docker 29.2.1; Compose 2.38.2; instalación/importaciones correctas; `pip check`: sin incompatibilidades. |
| F0: servicios y credenciales locales | `docker compose ps`; `/health`; GET stock sin/con Bearer leído de `.env`; conexión MySQL con PyMySQL | Ambos contenedores healthy; health 200; stock 401 sin token y 200 con token, 5 registros; MySQL 8.0.46/base `catalogo`, 0 tablas. |
| F0: remoto Git | `git push --dry-run origin HEAD:refs/heads/feature/etl-products` | Éxito; no se subieron cambios. |
| F1: normalización y configuración | `.venv/bin/python -m pytest -q`; `.venv/bin/ruff check src tests`; `.venv/bin/ruff format --check src tests` | 123 tests pasan; lint y formato correctos. Casos sintéticos sin BD/API. |
| F2: lector y selección diferida del catálogo | `.venv/bin/python -m pytest -q`; `.venv/bin/ruff check src tests`; `.venv/bin/ruff format --check src tests`; lectura aislada de `data/proveedor_productos.csv` | 155 tests en total; lint y formato correctos. Lectura real sin escribir fuentes ni BD. |
| F3: XML y coste neto | `.venv/bin/python -m pytest -q`; `.venv/bin/ruff check src tests`; `.venv/bin/ruff format --check src tests`; cruce en memoria de CSV/XML originales | 194 tests en total; lint y formato correctos. Ejemplo sintético 100 − 10 % − 5 % = 85; 115 productos seleccionados en memoria, sin BD. |
| F4: migración e integración MySQL | MySQL 8 temporal sin volumen del usuario; `F4_TEST_DB_PORT=… F4_TEST_DB_PASSWORD=… .venv/bin/python -m pytest -q`; Ruff; dos ejecuciones de `.venv/bin/python -m src.etl` con CSV/XML originales sobre la BD temporal | 201 tests pasan, Ruff limpio; UNIQUE/FK/CHECK, repetición, retiro/promoción, rollback, catálogo vacío, fichero cambiante, tarifa conflictiva y lock comprobados. 115 productos vigentes, 36 incidencias/run, estado de negocio idéntico. |
| F5: API mock, reglas y publicación de stock | `F4_TEST_DB_PORT=… F4_TEST_DB_PASSWORD=… .venv/bin/python -m pytest -q`; Ruff; dos comandos ETL contra la API local real con destino MySQL temporal | 273 tests pasan; lint/formato correctos. HTTP simulado cubre paginación, 401/403, 429 con segundos/fecha HTTP, 500, timeout, presupuesto, JSON/meta inválidos y páginas repetidas. Reglas cubren duplicados, versiones, conflictos, límites, reservas y NULL frente a cero. API real: 230 observaciones en 5 páginas; primer run necesitó un reintento en página 3, segundo ninguno. |
| MySQL, FKs y rollback | F4–F6 en MySQL 8 temporal; tests de pedidos sintéticos | PK/FKs/CHECK de almacenes y pedidos; repetición, corrección, históricos, promoción/retirada, instantánea vacía y rollback comprobados. |
| F6: pedidos y reconciliación | `.venv/bin/python -m pytest tests/integration -q`; tests unitarios; Ruff | 323 tests en total al cerrar F6: 302 unitarios y 21 MySQL. Unitarios: BOM/CSV, cabeceras, parciales y firmas. MySQL: históricos, promoción/retirada, FKs/CHECKs, repetición, corrección, instantánea vacía y rollback. |
| F7 inicial (v1): ETL completo y segunda ejecución | `F4_TEST_DB_PORT=… F4_TEST_DB_PASSWORD=… .venv/bin/python -m pytest -q`; Ruff; dos llamadas reales a `run_etl` en otra BD temporal vacía | 329 tests: 303 unitarios y 26 MySQL. F7 añade cinco casos E2E y una regresión de cliente con diferente capitalización. Cargas reales: 151 productos, 206 almacenes, 277 pedidos y 786 líneas idénticos; contadores e integridad correctos. |
| Corrección F6–F7: ADR 004 | Suite completa en MySQL temporal, Ruff y dos cargas reales v2 | 333 tests pasan (307 unitarios, 26 MySQL). 159 productos, 206 almacenes, 358 pedidos y 1.101 líneas idénticos entre cargas. Cero huérfanos, contadores conciliados y las 81 cabeceras restauradas. |
| F7: fallos y concurrencia | `tests/integration/test_etl.py` en MySQL 8, fuentes sintéticas | Última página 500 agotada y error real de FK tras escribir las cuatro tablas: negocio anterior íntegro, run failed durable, sin histórico ficticiamente creado en auditoría. Otro lector ve la versión previa antes del rollback. Segundo escritor rechazado antes de crear run durante extracción; tras liberar lock, nueva carga completada. |
| F8: SQL/conciliación de métricas | MySQL 8 temporal; `F4_TEST_DB_PORT=… F4_TEST_DB_NAME=f4_test_analytics F4_TEST_DB_PASSWORD=… .venv/bin/python -m pytest -q`; una carga real aislada y recálculo independiente con `as_of=2026-09-25`; Ruff | 339 tests pasan (307 sin BD, 32 MySQL), lint/formato correctos. Las consultas y el cálculo independiente coinciden en total, 18 meses/unidades, canales, categorías, top 10, margen, mes anterior y bajo stock. La comprobación real no alteró el volumen del usuario. |
| Web en navegador | TBD | TBD |
| Make con ejecución real y destinos | TBD | TBD |
| Arranque desde cero y secretos | TBD | TBD |

Trazabilidad de aceptación: A01 (cuatro fuentes y fallos), A02 (dos precios contrastados con origen), A03 (FKs e históricos), A04 (localizadores/contadores/rechazos) y A05 (repetición completa más corrección de líneas probada en F6) quedan verificados bajo las reglas vigentes. F8 acredita las consultas SQL de A07 y A08 bajo las decisiones documentadas; mostrar A07 en el dashboard es tarea F9. El margen estimado no equivale a beneficio confirmado por los conflictos de coste y la base fiscal pendiente.

## Qué cambiaría con cinco millones de líneas

Propuesta de evolución, pendiente de contrastar mediante medidas: lectura en streaming y staging MySQL por lotes, validación/deduplicación con índices y conjuntos en BD en vez de todo en memoria; publicación de versión consolidada solo tras validar; upserts/reconciliación por particiones o versión de snapshot; ID estable de línea del ERP para incrementar con seguridad. Medir EXPLAIN/índices y preagregar meses si las consultas lo necesitan. Definir retención/acceso de payloads e historial, backups y recuperación. Stock incremental con watermark y refresco completo periódico por falta de tombstones.

No introducir Spark/Kafka/Kubernetes solo por el número de filas: medir memoria, duración y cuellos antes. Decisiones finales, benchmark o estimaciones identificadas como tales: **TBD**.

## Limitaciones

Por validar: ausencia de ID de línea y coste histórico; base fiscal/zona de negocio; política de devoluciones; stock por instantánea y antigüedad; entrega Make al menos una vez. F5 conserva 12 productos sin stock observado como NULL y no crea productos por los 24 registros de stock ajenos al catálogo aceptado. El timestamp agregado es la actualización más reciente, no una garantía de frescura de todos los almacenes. La API no ofrece una versión de snapshot: totales iguales entre páginas no permiten detectar todo cambio concurrente del proveedor. Quedan por confirmar las reservas y la autoridad/frescura de la instantánea; más limitaciones de las fases futuras: **TBD**.

## Cosas dejadas fuera por tiempo

**TBD**: registrar lo realmente omitido. Candidatos opcionales: incremental, dockerización completa, YoY y mejoras operativas. No etiquetar un requisito obligatorio incumplido como «opcional»; indicarlo de forma explícita si finalmente falta.

## Uso de IA

Se usó Codex para inspeccionar el repositorio, redactar la planificación e implementar F0–F8. F1–F3 incorporaron reglas puras y Ruff; F4–F6 añadieron persistencia, stock y pedidos con pruebas MySQL y cargas parciales reales. F7 añadió pruebas de integración completa, un caso unitario que explicita la comparación actual de cliente, dos cargas reales de las cuatro fuentes y contraste de muestras contra origen. No modificó reglas de negocio, fuentes ni el volumen del usuario; corrigió el mensaje de error del CLI que aún mencionaba F5 y documentación desactualizada. El responsable deberá revisar y poder explicar las decisiones y resultados. Después de F7, el usuario confirmó equivalencia de capitalización del cliente: se implementó ADR 004, se versionaron reglas v2 y se repitieron suite y dos cargas reales. La deduplicación de las ocho repeticiones idénticas se mantuvo como decisión para la prueba. F8 añadió consultas SQL, seis pruebas MySQL sintéticas y contraste de métricas con una carga real aislada; detectó categorías con distinta capitalización y costes conflictivos con efecto material sobre el margen, documentados arriba.

Uso durante implementación, tareas asistidas, decisiones revisadas personalmente, validación y errores detectados: **TBD**. No atribuir aprobaciones o verificaciones humanas que no han ocurrido.

## Entrega y Git

- Enlace GitHub y acceso si privado: **TBD**.
- Ramas reales (mínimo tres de trabajo) y enlaces de PR merged a main (mínimo dos): **TBD**.
- Commit de main verificado y procedimiento reproducible: **TBD**.
- Resumen de dos o tres párrafos: **TBD**.
- Captura de panel con gráfico, escenario Make y ejecución correcta: **TBD**.
- Borrador de correo conforme al destinatario/asunto de README: **TBD**. Preparar no equivale a enviar; no se envía automáticamente.
