# Solución — documento vivo

**Estado: plantilla de entrega. F0–F6 comprobadas dentro de su alcance; dashboard y Make pendientes.** `TBD` significa pendiente de implementación/verificación; no sustituirlo por estimaciones presentadas como hechos.

Diseño propuesto: [PRD](PRD.md), [TECH_SPEC](TECH_SPEC.md), [DATA_RULES](DATA_RULES.md), [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md), [ADR](docs/adr/README.md). Al finalizar, actualizar esta guía a lo realmente implementado y distinguirlo de propuestas descartadas.

## Resumen

- Problema: consolidar catálogo CSV, tarifas XML, pedidos CSV y stock REST del distribuidor B2B.
- Funcionalidad realmente implementada: bootstrap de dependencias y comprobación local de servicios (F0); configuración, contratos y normalizadores puros (F1); lector/validador del CSV de catálogo (F2); reglas XML y coste neto calculado con selección definitiva por SKU en memoria (F3); migración MySQL y carga transaccional de catálogo/tarifas con auditoría (F4); API paginada y stock por almacén con publicación atómica de tres fuentes (F5); lector, normalización, históricos y reconciliación transaccional de pedidos (F6). Validación end-to-end completa: **TBD**.
- Versión/commit entregado y enlace GitHub: **TBD**.
- Estado de requisitos obligatorios y extras: **TBD**.

## Arquitectura final

El incremento implementado es CSV/XML/API de stock/CSV de pedidos → lectores y reglas Python → transacción InnoDB MySQL 8 (`products`, `stock_by_warehouse`, `orders`, `order_lines`, `etl_runs`, `rejections`). Las incidencias de fallos se confirman por separado tras rollback; un advisory lock serializa escritores. Diagrama final con web y Make: **TBD**.

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

El incremento F6 permite cargar las cuatro fuentes; todavía no hay web ni Make. La validación end-to-end completa corresponde a F7 y en F12 no pueden quedar pasos críticos implícitos.

### Dependencias elegidas en F0

`PyMySQL` proporciona el driver de MySQL que falta en la biblioteca estándar; `httpx` sirve tanto para la API como para el webhook y permite simular transporte en tests. `FastAPI`, `Uvicorn` y `Jinja2` sostendrán la página HTML propuesta, sin SPA ni ORM. `python-dotenv` permite cargar `.env` local sin ejecutarlo como shell ni sobrescribir variables; `pytest` verifica reglas futuras y `Ruff` configura un lint ligero. No se añade pandas, un segundo cliente HTTP ni un framework de migraciones. El uso de estas dependencias por módulos de aplicación queda pendiente de sus fases; F0 solo valida instalación/importación.

## Cómo ejecutar el ETL

- **Comando F6:** `.venv/bin/python -m src.etl` después de aplicar las migraciones. Usa también `ORDERS_CSV_PATH` (por defecto `data/pedidos_historico.csv`). Extrae las cuatro fuentes antes de abrir la transacción de negocio y publica pedidos, líneas e históricos junto con catálogo y stock. No envía Make.
- Código de salida `0`: publicación confirmada; puede haber filas rechazadas y quedan en `rejections`. Código `1`: fallo o concurrencia, sin publicar un catálogo parcial. Revisar `etl_runs` y las incidencias del `run_id` del log para fallos ocurridos tras crear el run. La caída antes de obtener el lock o antes de crear el run no genera auditoría de ejecución.
- Repetir el mismo comando con los mismos CSV/XML y respuestas completas de stock mantiene los valores de negocio y añade un `etl_runs`/sus incidencias nuevos. Los SKU que faltan en una instantánea válida pasan a históricos, con precios y stock `NULL`; un catálogo vacío o sin productos válidos, o un fichero modificado durante la extracción, falla y conserva la versión anterior. Solo se admite un escritor mediante advisory lock MySQL. Una caída abrupta puede dejar un run `running` para revisión manual.
- Parámetros opcionales de stock: `STOCK_PER_PAGE=50`, `STOCK_ATTEMPTS=5`, `STOCK_CONNECT_TIMEOUT=5`, `STOCK_READ_TIMEOUT=15`, `STOCK_REQUESTS_PER_MINUTE=30`, `STOCK_BUDGET_SECONDS=300`. Tiempos en segundos; límites y reintentos en [TECH_SPEC](TECH_SPEC.md#api-de-stock). No hace falta modificar `.env` para usar estos valores. ETL completo, dashboard y notificación: **TBD**.
- Reenvío a Make de un run confirmado sin repetir ETL: **TBD**.
- Recuperación automática adicional: **TBD**.

### Comprobación manual local de F6 (pendiente)

Las comprobaciones F5/F6 se hicieron en MySQL temporal; no se migró ni recargó la base `catalogo` del usuario. Para llevar este incremento a esa base, con los servicios activos y `.env` apuntando a ella:

```bash
.venv/bin/python -m src.db migrate
.venv/bin/python -m src.etl
```

Después, refrescar tablas en DBeaver. Debe aparecer `stock_by_warehouse`. Estas consultas permiten contrastar el último run y los totales; con las mismas fuentes usadas en esta prueba se esperan los resultados de la tabla de evidencias:

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

La comprobación manual en la base local y la integración de PR 3 siguen pendientes; F7 no se inicia por estos comandos.

## Cómo ejecutar tests

Las pruebas unitarias de F1–F6 se ejecutan sin BD ni API real; las pruebas de integración F4–F6 requieren un MySQL 8 separado:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
```

Sin `F4_TEST_DB_PORT`, los tests de integración se omiten. Para incluirlos, arrancar un contenedor temporal MySQL 8 **sin montar `mysql_data`**, con una base cuyo nombre empiece por `f4_test_`; pasar `F4_TEST_DB_PORT` y `F4_TEST_DB_PASSWORD` al proceso de pytest. Son opcionales `F4_TEST_DB_HOST` (127.0.0.1), `F4_TEST_DB_NAME` (`f4_test_catalog`) y `F4_TEST_DB_USER` (`f4_tester`). El test aplica la migración en esa base y crea solo datos sintéticos. No apuntarlo al volumen o base `catalogo` del usuario. Se conservan los nombres `F4_TEST_*` para las regresiones y los tests F5/F6. F6 se verificó con **323 tests pasando** en total (302 sin BD y 21 de integración MySQL); la lectura aislada del CSV real no modifica la fuente. Sin BD se omiten los 21 tests de integración. F7 corresponde a la validación end-to-end completa.

## Esquema de base de datos

F4 aplicó [`001_products_and_runs.sql`](db/migrations/001_products_and_runs.sql) en MySQL 8 aislado: `etl_runs` (PK UUID), `products` (PK numérica, SKU binario único y FK a run) y `rejections` (FK a run, UNIQUE por ejecución/fuente/localizador/motivo/campo). `DECIMAL` conserva precios y ratios; los `CHECK` controlan precios positivos, rangos, estado histórico y stock desconocido. La migración se registra en `schema_migrations`. Se verificaron `UNIQUE`, FK y `CHECK` con inserciones/actualizaciones inválidas en MySQL. F5 añade [`002_stock.sql`](db/migrations/002_stock.sql): `stock_by_warehouse` con PK producto/almacén, FK a producto/run y CHECK de cantidades y reservas no negativas; añade también `etl_runs.stock_sha256`. F6 añade [`003_orders.sql`](db/migrations/003_orders.sql): `orders` y `order_lines` con FKs, UNIQUE de pedido y firma de línea, CHECKs de dominios y `etl_runs.orders_sha256`. Los históricos mínimos mantienen la FK sin inventar atributos.

## Decisiones sobre calidad de datos

Reglas propuestas en [DATA_RULES](DATA_RULES.md): encoding por fuente, nulos, precios Decimal, EAN conservador, selección determinista de duplicados, descuentos, fechas, estados/canales y stock desconocido. En F1 se implantaron normalizadores puros para centinelas y texto, SKU/ID, decimales y dinero, descuentos, cantidades exactas, fechas y timestamps con zona, estados/canales observados, EAN y redondeo `ROUND_HALF_UP`. Un descuento sin `%` igual a `1` se interpreta como 1 %, según la decisión documentada. F2 lee el catálogo Latin-1 con `csv`, rechaza filas con columnas o campos obligatorios inválidos y descarta solo campos opcionales incorrectos. Conserva el coste CSV inválido como candidato condicionado a una excepción válida. F3 resuelve las tarifas, calcula el precio neto y entonces escoge la primera fila válida por SKU; los conflictos de tarifa general abortan el cálculo. F4 persiste el resultado en MySQL con auditoría. F5 integra stock conforme a la concreción de DATA_RULES: duplicados y versiones anteriores separados de rechazos, última observación por almacén, reservas sin restar, conflictos/errores con total inválido y ausencia con total desconocido. F6 lee 1.142 filas del histórico real sin modificarlo; en memoria quedaron 786 líneas aceptadas, 349 rechazadas y 7 deduplicadas, agrupadas en 277 pedidos, 22 parciales y 36 SKUs históricos potenciales. La validación end-to-end queda para F7.

La lectura aislada del catálogo original en F2 (sin tarifas ni MySQL) observó **133 registros de origen, 130 candidatos antes de precio final, 10 con coste CSV pendiente de validar por excepción y 13 incidencias preliminares**: 2 de columnas, 5 de campo obligatorio y 6 de EAN. Varios motivos pueden pertenecer a una sola fila. Eran cifras provisionales, antes de la selección económica de F3. Los ficheros de `data/` no se modificaron.

F3 cruza ese catálogo con el XML real. El parser reconoció 6 reglas de categoría, 10 de marca y 14 excepciones; registró 5 términos de volumen/condiciones no aplicados. El resultado seleccionó 115 productos con coste neto calculado (103 desde coste CSV y descuentos, 12 por excepción). Las 133 filas se reconcilian como **115 aceptadas + 15 rechazadas + 3 deduplicadas**. Hay 19 incidencias de acción «rechazar» porque una fila puede tener varios motivos; además hay 7 campos descartados y 7 avisos, incluidos 2 por excepciones sin candidato. F4 confirmó estas cifras con CSV/XML originales en una BD temporal: 115 productos vigentes y 36 incidencias persistidas por run. No es una ejecución de las cuatro fuentes. EUR y base fiscal comparable siguen sin confirmar.

## Definición de facturación y margen

Propuesta: ENVIADO/COMPLETADO con líneas válidas positivas, excluyendo cancelados, pendientes y devueltos; importe tras descuento de línea. Coste actual disponible para margen y cobertura visible cuando falta coste. No se conoce aún la base fiscal confirmada de los precios.

Decisión final, validación EUR/IVA, tratamiento de devoluciones, fecha de referencia, zona horaria y ejemplo real conciliado: **TBD**. Explicar pedidos parciales y desconocidos. No afirmar rentabilidad histórica exacta con costes actuales.

## Productos históricos

F4 conserva el ID de un producto que desaparece del CSV, lo marca histórico y limpia atributos comerciales, coste y stock. F6 crea/reutiliza el mismo ID para un SKU de pedido sin producto comercial, con atributos desconocidos a `NULL`; si reaparece en catálogo, lo promociona. Estas transiciones, FKs y retirada de pedidos pasaron contra MySQL con fixtures sintéticas. Medir cobertura de margen corresponde a F8.

## Idempotencia

F4 usa clave única SKU, upsert y reconciliación de catálogo completo con auditoría por run. F6 usa la firma `order-line-v1` y una instantánea completa de pedidos; las firmas idénticas se deduplican y las líneas/pedidos ausentes se retiran. Confirmación comercial de que el CSV es completo y política sobre dos líneas legítimas idénticas: **TBD**.

En el MySQL temporal, dos ejecuciones del comando con CSV/XML originales (`8c7c5ff3-f0ff-4171-8c60-334f896263a2` y `5ebade37-5a8d-4f66-9735-d8b50939a658`) dieron los mismos 115 productos vigentes y el mismo SHA-256 de la representación ordenada de sus campos de negocio: `80987e68f753c2f71d102802e2ceaf3f99b6693fcd53e17b56090c937face02e`. F6 verificó en MySQL sintético la repetición, corrección de una línea, retirada de pedidos ausentes, promoción/retirada de históricos y rollback después de publicar pedidos. La validación real de las cuatro fuentes y sus cifras queda para F7.

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

URL local/comando: **TBD**. Evidencia de catálogo, filtros, gráfico desde abril de 2025, KPIs, canal, top10, categorías, margen/cobertura y bajo stock: **TBD**. Captura real sin secretos: **TBD**. Comprobar coherencia con SQL y tratamiento visible de NULL/mes actual parcial: **TBD**.

## Resultados de ejecución

Esta tabla no contiene resultados previstos ni números simulados.

| Evidencia | Resultado real |
| --- | --- |
| Fecha/commit/reglas y entorno | F6, 24/09/2026, `catalog-stock-orders-v1`, MySQL 8 temporal; commit final de entrega TBD. |
| Hashes de entrada y fecha de referencia | CSV `ebe2a2079d02814b02b3094ef0e9c0d2c696b6a81c21172a8e0a2d2821d9159a`; XML `3922610e433d4b6e833a24f7e9db6d6c3c7858fbb8de4694d7fb005af511e3df`, iguales en ambos runs y guardados en `etl_runs`. Stock `08987b5f88455dc32034f60c331ed68ebbc94e4d3c33c312ae2f574e51b398bb`, también idéntico. Fecha analítica no aplica en F5. |
| run_id inicial / repetición y estados | `8b8d057e-70ce-48b7-ae64-b460ad55e954` / `3e50dd32-ae8e-4065-8c99-b860ff961e96`, ambos `completed` en `f4_test_real` temporal, sin fixtures previas. |
| Registros leídos por fuente | Catálogo CSV: 133; tarifas XML: reglas leídas, no filas CSV equivalentes. Stock: 230 en 5 páginas de 50. Pedidos: 1.142 filas reales leídas en memoria. |
| Productos aceptados/insertados/actualizados/sin cambio | 115 vigentes tras ambos runs; contadores de filas MySQL insertadas/actualizadas no se infieren de `affected_rows` y quedan TBD. |
| Productos históricos | 0 en estas ejecuciones F5; los casos de retiro/promoción se verifican con fixtures aparte. |
| Pedidos/líneas aceptados y pedidos parciales | F6: 1.142 filas reales leídas; 786 aceptadas, 349 rechazadas y 7 deduplicadas; 277 pedidos y 22 parciales en memoria. No se publicó el histórico real en esta fase. |
| Stock por almacén y productos con stock desconocido/inválido | 206 observaciones por almacén; 103 productos con stock conocido, 12 desconocido, 0 inválido. Cero huérfanos y cero diferencias entre total conocido y SUM(quantity) por producto. |
| Filas leídas/aceptadas/rechazadas/deduplicadas por fuente; avisos y campos descartados aparte | Catálogo: 133/115/15/3; stock: 230/206/24/0. Pedidos real en memoria: **1.142/786/349/7**; 31 avisos, sin campos descartados. Los 81 conflictos de cliente del histórico son diferencias solo de mayúsculas y se conservan como conflicto hasta confirmación; no se elige una variante silenciosamente. |
| Facturación, unidades, ticket y margen/cobertura | TBD |
| Duraciones y estado Make | TBD |
| Comparación de datos de negocio entre runs | 115 productos y 206 almacenes idénticos, incluidos IDs de producto y excluido `last_run_id`. SHA-256 de ambos conjuntos ordenados: `947b0b7a96e5a3fd111e513f608b2583a7d2706875cf821976395a07bec6bb69`. Hashes de fuentes y contadores idénticos entre runs. |

## Rechazos

Consulta de revisión: `SELECT source, record_locator, entity_key, reason_code, field_name, action FROM rejections WHERE run_id = ? ORDER BY id` (sustituir `?` por parámetro del cliente). El primer run real en la BD temporal persistió 36 incidencias: rechazos, deduplicaciones, avisos y campos descartados. `133 = 115 + 15 + 3`; los duplicados no cuentan como rechazos y una fila puede tener varios motivos. El detalle/payload de cada incidencia queda limitado; no se copia aquí ningún valor de proveedor. F5 añade 64 incidencias de stock por run real: 24 rechazos por SKU desconocido, 28 avisos de reservas superiores al físico y 12 avisos de ausencia. Total con catálogo/tarifas: 100 incidencias/run. Auditoría de pedidos: **TBD**.

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
| F6: pedidos y reconciliación | `.venv/bin/python -m pytest tests/integration -q`; tests unitarios; Ruff | 21 tests MySQL pasan: BOM/CSV, cabeceras, parciales, firmas, históricos, promoción/retirada, FKs/CHECKs, repetición, corrección, instantánea vacía y rollback. |
| ETL completo y segunda ejecución | TBD | TBD |
| SQL/conciliación de métricas | TBD | TBD |
| Web en navegador | TBD | TBD |
| Make con ejecución real y destinos | TBD | TBD |
| Arranque desde cero y secretos | TBD | TBD |

Los tests F4–F6 acreditan catálogo, tarifas, stock, pedidos y auditoría en una base temporal; no acreditan todavía la validación end-to-end de F7 ni las métricas de F8.

## Qué cambiaría con cinco millones de líneas

Propuesta de evolución, pendiente de contrastar mediante medidas: lectura en streaming y staging MySQL por lotes, validación/deduplicación con índices y conjuntos en BD en vez de todo en memoria; publicación de versión consolidada solo tras validar; upserts/reconciliación por particiones o versión de snapshot; ID estable de línea del ERP para incrementar con seguridad. Medir EXPLAIN/índices y preagregar meses si las consultas lo necesitan. Definir retención/acceso de payloads e historial, backups y recuperación. Stock incremental con watermark y refresco completo periódico por falta de tombstones.

No introducir Spark/Kafka/Kubernetes solo por el número de filas: medir memoria, duración y cuellos antes. Decisiones finales, benchmark o estimaciones identificadas como tales: **TBD**.

## Limitaciones

Por validar: ausencia de ID de línea y coste histórico; base fiscal/zona de negocio; política de devoluciones; stock por instantánea y antigüedad; entrega Make al menos una vez. F5 conserva 12 productos sin stock observado como NULL y no crea productos por los 24 registros de stock ajenos al catálogo aceptado. El timestamp agregado es la actualización más reciente, no una garantía de frescura de todos los almacenes. La API no ofrece una versión de snapshot: totales iguales entre páginas no permiten detectar todo cambio concurrente del proveedor. Quedan por confirmar las reservas y la autoridad/frescura de la instantánea; más limitaciones de las fases futuras: **TBD**.

## Cosas dejadas fuera por tiempo

**TBD**: registrar lo realmente omitido. Candidatos opcionales: incremental, dockerización completa, YoY y mejoras operativas. No etiquetar un requisito obligatorio incumplido como «opcional»; indicarlo de forma explícita si finalmente falta.

## Uso de IA

Se usó Codex para inspeccionar el repositorio y redactar la planificación; después, para implementar F0–F6. En F1–F3 se ejecutaron tests unitarios sintéticos y Ruff; F4 añadió tests de integración sintéticos en MySQL temporal y dos cargas de CSV/XML reales allí, sin modificar fuentes ni el volumen del usuario. F5 añadió HTTP simulado, consolidación de stock y pruebas MySQL, además de dos cargas reales de tres fuentes en otra base temporal. F6 añadió parser de pedidos, históricos y reconciliación con 21 pruebas MySQL. No se ha ejecutado todavía la validación end-to-end completa de F7. El responsable deberá revisar y poder explicar las decisiones y resultados.

Uso durante implementación, tareas asistidas, decisiones revisadas personalmente, validación y errores detectados: **TBD**. No atribuir aprobaciones o verificaciones humanas que no han ocurrido.

## Entrega y Git

- Enlace GitHub y acceso si privado: **TBD**.
- Ramas reales (mínimo tres de trabajo) y enlaces de PR merged a main (mínimo dos): **TBD**.
- Commit de main verificado y procedimiento reproducible: **TBD**.
- Resumen de dos o tres párrafos: **TBD**.
- Captura de panel con gráfico, escenario Make y ejecución correcta: **TBD**.
- Borrador de correo conforme al destinatario/asunto de README: **TBD**. Preparar no equivale a enviar; no se envía automáticamente.
