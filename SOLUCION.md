# Solución — documento vivo

**Estado: plantilla de entrega. F0–F4 comprobadas dentro de su alcance; stock, pedidos, dashboard y Make pendientes.** `TBD` significa pendiente de implementación/verificación; no sustituirlo por estimaciones presentadas como hechos.

Diseño propuesto: [PRD](PRD.md), [TECH_SPEC](TECH_SPEC.md), [DATA_RULES](DATA_RULES.md), [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md), [ADR](docs/adr/README.md). Al finalizar, actualizar esta guía a lo realmente implementado y distinguirlo de propuestas descartadas.

## Resumen

- Problema: consolidar catálogo CSV, tarifas XML, pedidos CSV y stock REST del distribuidor B2B.
- Funcionalidad realmente implementada: bootstrap de dependencias y comprobación local de servicios (F0); configuración, contratos y normalizadores puros (F1); lector/validador del CSV de catálogo (F2); reglas XML y coste neto calculado con selección definitiva por SKU en memoria (F3); migración MySQL y carga transaccional de catálogo/tarifas con auditoría (F4). Integración de cuatro fuentes: **TBD**.
- Versión/commit entregado y enlace GitHub: **TBD**.
- Estado de requisitos obligatorios y extras: **TBD**.

## Arquitectura final

El incremento implementado es CSV/XML → lectores y reglas Python → transacción InnoDB MySQL 8 (`products`, `etl_runs`, `rejections`). Las incidencias de fallos se confirman por separado tras rollback; un advisory lock serializa escritores. Diagrama final con stock, pedidos, web y Make: **TBD**.

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
6. Aplicar la migración F4 con `.venv/bin/python -m src.db migrate` una vez que `.env` apunte al MySQL deseado. Es idempotente y registra `001_products_and_runs` en `schema_migrations`; repetir el comando informa «ya aplicada». También sirve para un volumen existente sin borrar el volumen: `db/init` solo se ejecuta al inicializarlo. Antes de cualquier migración sobre una BD con datos propios, respaldarla y revisar si ya existen tablas con los mismos nombres. Las migraciones posteriores: **TBD**.
7. Arrancar web: comando, host/puerto y URL local **TBD**.
8. Registrar validación desde clon/BD de pruebas nuevos, fecha y commit: **TBD**. No ejecutar pruebas destructivas sobre el volumen del usuario.

El incremento F4 permite cargar únicamente catálogo y tarifas; todavía no hay web ni ETL de las cuatro fuentes. En F12 no pueden quedar pasos críticos implícitos.

### Dependencias elegidas en F0

`PyMySQL` proporciona el driver de MySQL que falta en la biblioteca estándar; `httpx` sirve tanto para la API como para el webhook y permite simular transporte en tests. `FastAPI`, `Uvicorn` y `Jinja2` sostendrán la página HTML propuesta, sin SPA ni ORM. `python-dotenv` permite cargar `.env` local sin ejecutarlo como shell ni sobrescribir variables; `pytest` verifica reglas futuras y `Ruff` configura un lint ligero. No se añade pandas, un segundo cliente HTTP ni un framework de migraciones. El uso de estas dependencias por módulos de aplicación queda pendiente de sus fases; F0 solo valida instalación/importación.

## Cómo ejecutar el ETL

- **Comando parcial F4:** `.venv/bin/python -m src.etl` después de aplicar la migración. Usa `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `CSV_PATH` y `XML_PATH` de `.env`/entorno. La configuración F1 aún exige `STOCK_API_URL` y `STOCK_API_TOKEN`, aunque F4 no llama a esa API. No lee pedidos ni stock, ni envía Make.
- Código de salida `0`: publicación confirmada; puede haber filas rechazadas y quedan en `rejections`. Código `1`: fallo o concurrencia, sin publicar un catálogo parcial. Revisar `etl_runs` y las incidencias del `run_id` del log para fallos ocurridos tras crear el run. La caída antes de obtener el lock o antes de crear el run no genera auditoría de ejecución.
- Repetir el mismo comando con los mismos CSV/XML válidos mantiene los valores de negocio y añade un `etl_runs`/sus incidencias nuevos. Los SKU que faltan en una instantánea válida pasan a históricos, con precios y stock `NULL`; un catálogo vacío o sin productos válidos, o un fichero modificado durante la extracción, falla y conserva la versión anterior. Solo se admite un escritor mediante advisory lock MySQL. Una caída abrupta puede dejar un run `running` para revisión manual.
- Variables/rutas de pedidos y stock, ETL completo y notificación: **TBD**.
- Reenvío a Make de un run confirmado sin repetir ETL: **TBD**.
- Recuperación automática adicional: **TBD**.

## Cómo ejecutar tests

Las pruebas unitarias de F1–F3 se ejecutan sin BD ni API; las pruebas F4 requieren un MySQL 8 separado:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
```

Sin `F4_TEST_DB_PORT`, los tests de integración se omiten. Para incluirlos, arrancar un contenedor temporal MySQL 8 **sin montar `mysql_data`**, con una base cuyo nombre empiece por `f4_test_`; pasar `F4_TEST_DB_PORT` y `F4_TEST_DB_PASSWORD` al proceso de pytest. Son opcionales `F4_TEST_DB_HOST` (127.0.0.1), `F4_TEST_DB_NAME` (`f4_test_catalog`) y `F4_TEST_DB_USER` (`f4_tester`). El test aplica la migración en esa base y crea solo datos sintéticos. No apuntarlo al volumen o base `catalogo` del usuario. F4 se verificó así en un contenedor temporal con puerto local dinámico; 201 tests pasaron. La lectura de pedidos corresponde a F6 y la API a F5.

## Esquema de base de datos

F4 aplicó [`001_products_and_runs.sql`](db/migrations/001_products_and_runs.sql) en MySQL 8 aislado: `etl_runs` (PK UUID), `products` (PK numérica, SKU binario único y FK a run) y `rejections` (FK a run, UNIQUE por ejecución/fuente/localizador/motivo/campo). `DECIMAL` conserva precios y ratios; los `CHECK` controlan precios positivos, rangos, estado histórico y stock desconocido. La migración se registra en `schema_migrations`. Se verificaron `UNIQUE`, FK y `CHECK` con inserciones/actualizaciones inválidas en MySQL. `orders`, `order_lines` y stock por almacén siguen **TBD** para F5–F6; el diagrama final también.

## Decisiones sobre calidad de datos

Reglas propuestas en [DATA_RULES](DATA_RULES.md): encoding por fuente, nulos, precios Decimal, EAN conservador, selección determinista de duplicados, descuentos, fechas, estados/canales y stock desconocido. En F1 se implantaron normalizadores puros para centinelas y texto, SKU/ID, decimales y dinero, descuentos, cantidades exactas, fechas y timestamps con zona, estados/canales observados, EAN y redondeo `ROUND_HALF_UP`. Un descuento sin `%` igual a `1` se interpreta como 1 %, según la decisión documentada. F2 lee el catálogo Latin-1 con `csv`, rechaza filas con columnas o campos obligatorios inválidos y descarta solo campos opcionales incorrectos. Conserva el coste CSV inválido como candidato condicionado a una excepción válida. F3 resuelve las tarifas, calcula el precio neto y entonces escoge la primera fila válida por SKU; los conflictos de tarifa general abortan el cálculo. F4 persiste el resultado en MySQL con auditoría; pedidos y stock: **TBD**.

La lectura aislada del catálogo original en F2 (sin tarifas ni MySQL) observó **133 registros de origen, 130 candidatos antes de precio final, 10 con coste CSV pendiente de validar por excepción y 13 incidencias preliminares**: 2 de columnas, 5 de campo obligatorio y 6 de EAN. Varios motivos pueden pertenecer a una sola fila. Eran cifras provisionales, antes de la selección económica de F3. Los ficheros de `data/` no se modificaron.

F3 cruza ese catálogo con el XML real. El parser reconoció 6 reglas de categoría, 10 de marca y 14 excepciones; registró 5 términos de volumen/condiciones no aplicados. El resultado seleccionó 115 productos con coste neto calculado (103 desde coste CSV y descuentos, 12 por excepción). Las 133 filas se reconcilian como **115 aceptadas + 15 rechazadas + 3 deduplicadas**. Hay 19 incidencias de acción «rechazar» porque una fila puede tener varios motivos; además hay 7 campos descartados y 7 avisos, incluidos 2 por excepciones sin candidato. F4 confirmó estas cifras con CSV/XML originales en una BD temporal: 115 productos vigentes y 36 incidencias persistidas por run. No es una ejecución de las cuatro fuentes. EUR y base fiscal comparable siguen sin confirmar.

## Definición de facturación y margen

Propuesta: ENVIADO/COMPLETADO con líneas válidas positivas, excluyendo cancelados, pendientes y devueltos; importe tras descuento de línea. Coste actual disponible para margen y cobertura visible cuando falta coste. No se conoce aún la base fiscal confirmada de los precios.

Decisión final, validación EUR/IVA, tratamiento de devoluciones, fecha de referencia, zona horaria y ejemplo real conciliado: **TBD**. Explicar pedidos parciales y desconocidos. No afirmar rentabilidad histórica exacta con costes actuales.

## Productos históricos

F4 conserva el ID de un producto que desaparece del CSV, lo marca histórico y limpia atributos comerciales, coste y stock. Si reaparece, actualiza el mismo ID y recupera el estado vigente; ambas transiciones pasaron contra MySQL con fixture sintética. Crear históricos por SKUs de pedidos y medir cobertura de margen: **TBD** para F6/F8. Los 2 históricos observados en la prueba con fuentes reales provenían de fixtures sintéticas cargadas antes en la misma BD temporal; no se atribuyen al proveedor.

## Idempotencia

F4 usa clave única SKU, upsert y reconciliación de catálogo completo con auditoría por run. La firma de línea y la reconciliación de pedidos son **TBD**. Confirmación comercial de que CSV es completo y política sobre dos líneas legítimas idénticas: **TBD**.

En el MySQL temporal, dos ejecuciones del comando con CSV/XML originales (`8c7c5ff3-f0ff-4171-8c60-334f896263a2` y `5ebade37-5a8d-4f66-9735-d8b50939a658`) dieron los mismos 115 productos vigentes y el mismo SHA-256 de la representación ordenada de sus campos de negocio: `80987e68f753c2f71d102802e2ceaf3f99b6693fcd53e17b56090c937face02e`. Se excluyeron `last_run_id` y otros metadatos. La prueba de integración forzó un fallo después de los upserts y verificó rollback del negocio, nuevo run `failed` e incidencia; también comprobó que un CSV alterado durante la lectura no se publica. La corrección de líneas y el stock completo son **TBD**.

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
| Fecha/commit/reglas y entorno | F4, 24/09/2026, `catalog-pricing-v1`, MySQL 8 temporal; commit final de entrega TBD. |
| Hashes de entrada y fecha de referencia | CSV `ebe2a2079d02814b02b3094ef0e9c0d2c696b6a81c21172a8e0a2d2821d9159a`; XML `3922610e433d4b6e833a24f7e9db6d6c3c7858fbb8de4694d7fb005af511e3df`, iguales en ambos runs y guardados en `etl_runs`. Fecha analítica no aplica en F4. |
| run_id inicial / repetición y estados | `8c7c5ff3-f0ff-4171-8c60-334f896263a2` / `5ebade37-5a8d-4f66-9735-d8b50939a658`, ambos `completed` en BD temporal. |
| Registros leídos por fuente | Catálogo CSV: 133; tarifas XML: reglas leídas, no filas CSV equivalentes. Stock/pedidos TBD. |
| Productos aceptados/insertados/actualizados/sin cambio | 115 vigentes tras ambos runs; contadores de filas MySQL insertadas/actualizadas no se infieren de `affected_rows` y quedan TBD. |
| Productos históricos | TBD |
| Pedidos/líneas aceptados y pedidos parciales | TBD |
| Stock por almacén y productos con stock desconocido/inválido | TBD |
| Filas leídas/aceptadas/rechazadas/deduplicadas por fuente; avisos y campos descartados aparte | Catálogo: 133/115/15/3; 7 avisos y 7 campos descartados. Otras fuentes TBD. |
| Facturación, unidades, ticket y margen/cobertura | TBD |
| Duraciones y estado Make | TBD |
| Comparación de datos de negocio entre runs | 115 vigentes y huella ordenada idéntica (`80987e68…face02e`), excluidos IDs de run. |

## Rechazos

Consulta F4 de revisión: `SELECT source, record_locator, entity_key, reason_code, field_name, action FROM rejections WHERE run_id = ? ORDER BY id` (sustituir `?` por parámetro del cliente). El primer run real en la BD temporal persistió 36 incidencias: rechazos, deduplicaciones, avisos y campos descartados. `133 = 115 + 15 + 3`; los duplicados no cuentan como rechazos y una fila puede tener varios motivos. El detalle/payload de cada incidencia queda limitado; no se copia aquí ningún valor de proveedor. Auditoría de stock/pedidos: **TBD**.

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
| API mock, paginación y errores | TBD | TBD |
| MySQL, FKs y rollback | F4 parcial, ver fila anterior; relaciones de pedidos/stock TBD. | F4 verificado contra MySQL 8. |
| ETL completo y segunda ejecución | TBD | TBD |
| SQL/conciliación de métricas | TBD | TBD |
| Web en navegador | TBD | TBD |
| Make con ejecución real y destinos | TBD | TBD |
| Arranque desde cero y secretos | TBD | TBD |

Los tests F4 acreditan persistencia e integridad solo del catálogo y auditoría; no acreditan todavía el ETL completo.

## Qué cambiaría con cinco millones de líneas

Propuesta de evolución, pendiente de contrastar mediante medidas: lectura en streaming y staging MySQL por lotes, validación/deduplicación con índices y conjuntos en BD en vez de todo en memoria; publicación de versión consolidada solo tras validar; upserts/reconciliación por particiones o versión de snapshot; ID estable de línea del ERP para incrementar con seguridad. Medir EXPLAIN/índices y preagregar meses si las consultas lo necesitan. Definir retención/acceso de payloads e historial, backups y recuperación. Stock incremental con watermark y refresco completo periódico por falta de tombstones.

No introducir Spark/Kafka/Kubernetes solo por el número de filas: medir memoria, duración y cuellos antes. Decisiones finales, benchmark o estimaciones identificadas como tales: **TBD**.

## Limitaciones

Por validar: ausencia de ID de línea y coste histórico; base fiscal/zona de negocio; política de devoluciones; stock por instantánea y antigüedad; entrega Make al menos una vez. Limitaciones realmente encontradas, impacto y mitigación: **TBD**.

## Cosas dejadas fuera por tiempo

**TBD**: registrar lo realmente omitido. Candidatos opcionales: incremental, dockerización completa, YoY y mejoras operativas. No etiquetar un requisito obligatorio incumplido como «opcional»; indicarlo de forma explícita si finalmente falta.

## Uso de IA

Se usó Codex para inspeccionar el repositorio y redactar la planificación; después, para implementar F0–F4. En F1–F3 se ejecutaron tests unitarios sintéticos y Ruff; F4 añadió tests de integración sintéticos en MySQL temporal y dos cargas de CSV/XML reales allí, sin modificar fuentes ni el volumen del usuario. No se ha implementado ni ejecutado el ETL completo. El responsable deberá revisar y poder explicar las decisiones y resultados.

Uso durante implementación, tareas asistidas, decisiones revisadas personalmente, validación y errores detectados: **TBD**. No atribuir aprobaciones o verificaciones humanas que no han ocurrido.

## Entrega y Git

- Enlace GitHub y acceso si privado: **TBD**.
- Ramas reales (mínimo tres de trabajo) y enlaces de PR merged a main (mínimo dos): **TBD**.
- Commit de main verificado y procedimiento reproducible: **TBD**.
- Resumen de dos o tres párrafos: **TBD**.
- Captura de panel con gráfico, escenario Make y ejecución correcta: **TBD**.
- Borrador de correo conforme al destinatario/asunto de README: **TBD**. Preparar no equivale a enviar; no se envía automáticamente.
