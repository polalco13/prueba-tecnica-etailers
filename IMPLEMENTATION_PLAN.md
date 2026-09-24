# Plan de implementación y estrategia Git

Estado actualizado tras F5: F0–F4 integradas; F5 implementada y verificada en `feature/etl-stock`, pendiente de PR 2 e integración. F6 y siguientes no iniciadas. La evidencia ejecutada está en [SOLUCION](SOLUCION.md); las tareas futuras siguen siendo planificación. Referencias: [PRD](PRD.md), [TECH_SPEC](TECH_SPEC.md), [DATA_RULES](DATA_RULES.md), [AGENTS](AGENTS.md). Cada fase se solicita y verifica por separado; no empezar la siguiente automáticamente.

## Orden y alcance

Ruta obligatoria: F0 → F1 → F2 → F3 → F4 → F5 → F6 → F7 → F8 → F9 → F10 → F12. F11 es opcional después de F10 y no bloquea entrega. No interpretar trece fases como trece días: son cortes pequeños para el plazo del README. Si falta tiempo, reducir extras F11 y estética, no Make ni métricas requeridas.

Las fases preparan primero reglas puras y después persistencia, integración, SQL y web. Cada cierre exige actualizar decisiones y evidencia en SOLUCION sin inventar resultados. Nombres de módulos, comandos, ramas y commits siguientes son propuestas, no archivos o acciones ya ejecutadas. Con el plazo del README, reservar tiempo desde F0 para credenciales y acceso a los destinos de Make, y desde F7 para una ejecución completa y contraste manual de resultados; F11 solo se considera si lo obligatorio ya funciona.

## F0 — Bootstrap y validación del entorno

- **Objetivo:** entorno reproducible, dependencias mínimas y límites conocidos antes de escribir lógica.
- **Tareas:** releer documentos; revisar `git status` y preservar cambios del usuario; comprobar Docker y Python propuesto; conservar `.env` si existe, crear desde ejemplo solo si falta; verificar variables sin mostrarlas. Levantar Compose existente si es necesario, healthcheck de MySQL y API, lectura autenticada de una página. No copiar logs del mock que contienen token. Inventariar esquema existente antes de tocar BD. Fijar dependencias justificadas, configuración de pytest y lint opcional. Confirmar acceso GitHub, Make y dos destinos previstos, además de destinatario de alerta; registrar cualquier dependencia externa pendiente desde el inicio, sin enviar mensajes.
- **Archivos previstos:** `pyproject.toml`, archivo de versiones resueltas según herramienta elegida, `.gitignore` solo mediante cambio deliberado, `SOLUCION.md`; `.env` exclusivamente local. `.env.example`/Compose solo si la tarea futura autoriza ampliar configuración y se documenta la necesidad.
- **Tests/verificación:** versiones, importación de dependencias, `docker compose ps`, `/health`, autenticación positiva/negativa sin imprimir tokens y conexión DB. La API puede fallar transitoriamente; registrar fallo, no afirmar éxito. No se requiere escribir tests artificiales para comandos de arranque.
- **Finalización:** servicios sanos y conexión documentada; discrepancia `.env`/Compose entendida; disponibilidad o bloqueo concreto de Make/destinos conocidos desde el inicio; ninguna credencial añadida a Git; comandos reales del entorno en SOLUCION.
- **Commits sugeridos:** `chore: define Python dependencies and test configuration`; `docs: document verified local startup`.
- **Rama / PR:** `feature/etl-products`, PR 1 junto con F1–F4.
- **Dependencias:** documentos de planificación; Docker disponible. Si un servicio no está accesible, cerrar solo la parte comprobada y mantener F0 pendiente.

## F1 — Fundamentos y normalizadores

- **Objetivo:** reglas puras probadas antes de ingerir fuentes completas.
- **Tareas:** configuración/validación de entorno, logging saneado, contratos de registro e incidencia; `parse_money`, `parse_decimal`, `parse_discount`, nulos, strings, identificadores, fechas, estados/canales observados, EAN y redondeo. Definir códigos estables, severidad/acción y límites. Resolver zona horaria propuesta.
- **Archivos previstos:** `src/config.py`, `src/etl/records.py`, `src/etl/normalize.py`, inicializadores de paquete, `tests/unit/test_normalize.py`, `tests/unit/test_config.py`, `tests/fixtures/`.
- **Tests:** tabla de casos de DATA_RULES: encodings, 10%/10/0,1 y 1 ambiguo, importes europeos/anglosajones inequívocos, miles ambiguos rechazados, cantidades `2,0`/`2.0` como 2 y `2,5` inválida, NaN/rango, EAN válido/checksum/scientific y apóstrofo inicial, fechas imposibles/bisiestas, centinelas vs guion dentro de SKU, Decimal y redondeo en medio céntimo. Comprobar que secretos no entran en errores/logs.
- **Finalización:** todos los tests relacionados pasan, normalización determinista e independiente de DB/HTTP; cada regla relevante tiene caso positivo y negativo. No avanzar con reglas pendientes ocultas.
- **Commits sugeridos:** `feat: add typed configuration and safe logging`; `feat: add tested data normalizers`.
- **Rama / PR:** `feature/etl-products`, PR 1.
- **Dependencias:** F0.

## F2 — Catálogo de productos

- **Objetivo:** extraer candidatos y problemas de calidad conservando procedencia.
- **Tareas:** lector Latin-1/`;`, cabecera/columnas/quoting, campos obligatorios y opcionales, EAN con descarte de campo; deduplicar filas idénticas y escoger la primera fila válida por SKU, registrando los conflictos; preparar contrato para que F3 valide precio final antes de seleccionar. No persistir todavía ni modificar data.
- **Archivos previstos:** `src/etl/catalog.py`, `tests/unit/test_catalog.py`, fixtures CSV pequeñas.
- **Tests:** columnas de más/menos, registro multilínea, SKU vacío, EAN con apóstrofo inicial válido frente a EAN científico o con checksum inválido, opcionales inválidos, duplicados exactos; primer candidato inválido seguido de uno válido, dos válidos conflictivos y procedencia del descartado. Coste inválido queda candidato condicionado a excepción válida de F3, no aceptado como producto comercial por sí solo.
- **Finalización:** salida de candidatos/incidencias explicable y estable en fixtures; archivo original sin cambios; contrato de coste condicionado explícito.
- **Commits sugeridos:** `feat: parse catalog with row provenance`; `feat: resolve catalog candidates deterministically`.
- **Rama / PR:** `feature/etl-products`, PR 1.
- **Dependencias:** F1.

## F3 — Tarifas y precio neto

- **Objetivo:** resolver coste de compra y seleccionar productos válidos.
- **Tareas:** parser XML, reglas categoría/marca y excepción SKU; combinación aditiva propuesta, ausencia vs regla inválida, conflictos, redondeo; reconocer volumen/condiciones sin aplicarlos. Cruzar candidatos y validar precio antes de elegir SKU ganador. Confirmar o documentar fórmula propuesta.
- **Archivos previstos:** `src/etl/pricing.py`, ajuste de `catalog.py`, `tests/unit/test_pricing.py`, fixture XML, DATA_RULES si cambia decisión.
- **Tests:** excepción evita todo descuento; coste base inválido con/sin excepción; categoría+marca, solo una/ninguna, texto normalizado, regla general inválida o contradictoria falla la ejecución sin publicar coste, suma >=100%, regla idéntica deduplicada, excepción huérfana y XML roto. Caso calculado manualmente 100/10%/5% = 85, identificado como fixture ficticia.
- **Finalización:** precios comprobados con resultados esperados independientes; productos inválidos y tarifas no aplicadas explicados; nada de float.
- **Commits sugeridos:** `feat: parse supplier pricing rules`; `feat: calculate net costs with explicit precedence`.
- **Rama / PR:** `feature/etl-products`, PR 1.
- **Dependencias:** F2.

## F4 — Persistencia de productos y auditoría

- **Objetivo:** primer incremento ejecutable de catálogo/tarifas en MySQL.
- **Tareas:** scripts versionados para products, etl_runs y rejections; conexión, transacción, UNIQUE/constraints, upsert, incidencias y contadores; comando inicial limitado a catálogo/tarifas claramente documentado. Introducir protección frente a concurrencia y estado de run fallido. No prometer aún ETL completo. Documentar aplicación de esquema en volumen existente.
- **Archivos previstos:** `db/migrations/001_products_and_runs.sql`, `src/db.py`, `src/etl/repository.py`, `runner.py`, `__main__.py`, `reporting.py`, `tests/integration/test_products.py`.
- **Tests:** MySQL de pruebas separado; carga dos veces, mismo contenido sin duplicados; UNIQUE real, precios/rangos, rollback forzado, persistencia de incidencias y estado failed, snapshot de catálogo inesperadamente vacío no borra datos previos, contadores no basados en affected_rows.
- **Finalización:** comando documentado carga catálogo/tarifas y rechazos; repetir mantiene negocio; tests pasan contra MySQL 8; PR 1 revisable con alcance explícito y main funcional para ese incremento.
- **Commits sugeridos:** `feat: add versioned product and audit schema`; `feat: persist catalog snapshots idempotently`.
- **Rama / PR:** `feature/etl-products`, cerrar PR 1 a `main`.
- **Dependencias:** F3.

## F5 — Stock

- **Objetivo:** integrar una instantánea completa de stock sin falsear ceros ni totales.
- **Tareas:** cliente aislado, autenticación/páginas/timeouts; 500/429, Retry-After, backoff acotado y limitación de tasa; validación de respuesta y filas, última observación por almacén, conflictos, SKU desconocido, suma quantity y reservado aparte; persistencia de almacenes y estado unknown/invalid/known. Actualizar comando parcial para tres fuentes.
- **Archivos previstos:** `src/etl/stock_client.py`, `stock.py`, repositorio/runner, `db/migrations/002_stock.sql`, `tests/unit/test_stock_client.py`, `test_stock.py`, `tests/integration/test_stock.py`.
- **Tests:** transporte httpx simulado; varias páginas, vacía, 401 sin retry, 500 recuperable/agotado, 429 con `Retry-After`, timeout y meta inconsistente; almacenes repetidos, cantidades negativas rechazadas, `reserved > quantity` conservado con aviso, stock ausente vs 0. Fallo de última página conserva toda la versión de negocio anterior.
- **Finalización:** stock completo para SKUs válidos, desconocidos auditados; prueba real de API local documentada; ninguna publicación parcial ni bucle infinito. Retry básico queda hecho, no pospuesto a F11.
- **Commits sugeridos:** `feat: fetch paginated stock with bounded retries`; `feat: reconcile warehouse stock and unknown totals`.
- **Rama / PR:** `feature/etl-stock`, PR 2 a `main`.
- **Dependencias:** F4 integrado.

## F6 — Pedidos históricos

- **Objetivo:** relacionar pedidos y productos sin perder históricos ni duplicar líneas.
- **Tareas:** UTF-8 BOM, estructura CSV, agrupar cabeceras, herencia controlada de vacíos, conflictos, estados/canales, cantidades y descuentos; firma determinista/dedupe, productos históricos, FKs, reconciliación de snapshot y pedidos parciales. Confirmar supuesto de exportación completa e identidad de línea. Integrar cuatro fuentes en una transacción de negocio, auditoría separada de errores.
- **Archivos previstos:** `src/etl/orders.py`, repositorio/runner/reporting, `db/migrations/003_orders.sql`, `tests/unit/test_orders.py`, `tests/integration/test_orders.py`, fixtures.
- **Tests:** cabecera con fecha con/sin hora, vacío recuperable/no recuperable, valores contradictorios, cliente ausente; cantidades `2,0` y `2.0` aceptadas como 2, `2,5` rechazada, negativos DEVUELTO vs COMPLETADO, dos precios distintos mismo SKU, firma estable, duplicado idéntico, corrección de línea elimina anterior, pedido ausente retirado, histórico reutilizado/promovido, pedido parcial y pedido sin líneas, FKs reales y rollback.
- **Finalización:** todas las líneas cargadas tienen producto válido y política económica explícita; snapshot completo repetible; limitación de dos líneas legítimas idénticas documentada con impacto observado, si lo hay, sin inventar cifras.
- **Commits sugeridos:** `feat: normalize order headers and signed lines`; `feat: preserve historical products and reconcile orders`.
- **Rama / PR:** `feature/orders`, PR 3 junto con F7.
- **Dependencias:** F5 integrado.

## F7 — Validaciones end-to-end

- **Objetivo:** demostrar integridad y repetibilidad del ETL antes de calcular métricas.
- **Tareas:** prueba completa con entradas congeladas; reconciliar leídos/aceptados/descartados e incidencias; seguir manualmente una muestra de filas de cada fuente hasta la BD, incluyendo valores normalizados y rechazos; comparar valores y conteos de negocio entre ejecuciones, excluyendo auditoría; fallo durante extracción y durante carga; verificar política de concurrencia. Registrar evidencias reales en SOLUCION.
- **Archivos previstos:** `tests/integration/test_etl.py`, fixtures controladas, consultas de verificación de solo lectura en tests, `SOLUCION.md`; cambios de runner solo para corregir fallos encontrados.
- **Tests:** cero huérfanos, UNIQUEs, stock suma válida, coste neto esperado, hashes/conjuntos equivalentes, auditoría nueva en segunda ejecución y rollback sin estado mixto. Comprobar por fuente `rows_read = rows_accepted + rows_rejected + rows_deduplicated`; una ejecución con solo duplicados debe tener `rows_rejected=0`. Con fuentes reales no forzar conteos de fixtures; observar y registrar los reales, revisar si hay pérdidas inesperadas por motivo y explicar los casos encontrados.
- **Finalización:** checks críticos pasan y resultados reales respaldan A01–A05; ninguna discrepancia de reconciliación sin explicar. Cerrar PR 3.
- **Commits sugeridos:** `test: verify complete ETL integrity and repeatability`; `docs: record observed ETL validation evidence`.
- **Rama / PR:** `feature/orders`, PR 3 a `main`.
- **Dependencias:** F6.

## F8 — Consultas analíticas

- **Objetivo:** números verificables antes de la interfaz.
- **Tareas:** SQL para evolución mensual de importe/unidades, facturación/pedidos/ticket, canal, top 10, categoría, margen conocido/cobertura y stock <5 con ventas en últimos tres meses; mes anterior para Make. Centralizar elegibilidad, intervalos y fecha de referencia. Validar base fiscal/EUR o mostrar limitación.
- **Archivos previstos:** `src/analytics/__init__.py`, `queries.py`, `tests/integration/test_analytics.py`, fixtures de negocio calculadas a mano.
- **Tests:** unión sin multiplicar por almacenes, meses vacíos/actual parcial, ventana móvil y último día de mes, devolución/cancelación excluidas, histórico con coste NULL, margen negativo válido, pedido parcial, ticket sin pedidos, desempate de top10; suma por canal/categoría = total y subtotal de margen calculado independientemente. Contrastar manualmente una muestra de meses y líneas con los datos de origen y consultar cualquier salto inexplicado de la serie antes de atribuirlo a estacionalidad.
- **Finalización:** todas las métricas exigidas tienen consulta y test independiente; resultado revisable directamente en SQL; ninguna métrica se rellena con datos inventados para mostrar estacionalidad.
- **Commits sugeridos:** `feat: add reconciled sales analytics queries`; `test: cover margin and low-stock reporting boundaries`.
- **Rama / PR:** `feature/dashboard`, PR 4 junto con F9.
- **Dependencias:** F7 integrado.

## F9 — Dashboard

- **Objetivo:** catálogo y panel sencillo alimentados exclusivamente por MySQL.
- **Tareas:** FastAPI/HTML, listado paginado con nombre/SKU/neto/PVP/stock/categoría, búsqueda por SKU/nombre/descripción y filtro categoría combinables; KPIs, Chart.js para importe/unidades, canal, rankings, margen/cobertura y bajo stock. Mostrar estados vacíos, error DB, última actualización, stock desconocido, criterio de facturación y pedidos parciales.
- **Archivos previstos:** `src/web/app.py`, `templates/index.html`, `static/`, `tests/integration/test_web.py`, `SOLUCION.md`.
- **Tests:** filtros combinados/paginación, consulta parametrizada, HTML escapado, respuesta vacía/error controlado; contraste de valores web con SQL validado. Verificación manual en navegador del gráfico, ejes, meses y legibilidad; capturar solo pantalla real sin datos sensibles.
- **Finalización:** A06–A08, todos los campos y estadísticas del README visibles, sin lógica económica duplicada en JS; captura real del panel disponible. Cerrar PR 4.
- **Commits sugeridos:** `feat: expose searchable catalog page`; `feat: render business KPIs and monthly sales chart`.
- **Rama / PR:** `feature/dashboard`, PR 4 a `main`.
- **Dependencias:** F8.

## F10 — Integración Make

- **Objetivo:** una ejecución real del ETL distribuida a destinos útiles.
- **Tareas:** contrato/versionado del resumen guardado, cliente webhook posterior al commit y reenvío por run_id; escenario webhook, router/filtro, email condicional e histórico siempre en Sheets; umbral explícito, deduplicación de histórico. Confirmar cuentas, conexiones y destinatario sin versionar secretos. Exportar blueprint real, capturas del escenario y ejecución de destinos; documentar disparador/decisiones. El envío de correos por herramientas requiere instrucción explícita del usuario: preparar primero destinatario y contenido de prueba revisables.
- **Archivos previstos:** `src/etl/make_client.py`, `reporting.py`, runner/config, `tests/unit/test_make_client.py`, `make/escenario.blueprint.json`, `make/capturas/`, `make/README.md`, `SOLUCION.md`.
- **Tests:** resumen coincide con run/SQL, serialización Decimal, timeout/500/fallo sin rollback del ETL, mismo run_id al reintentar; un resumen con `rows_deduplicated>0`, `rows_rejected=0` y sin bajo stock va solo al histórico. Ejecución real verifica histórico y alerta cuando corresponde, incluida prueba controlada de umbral marcada como tal. HTTP 2xx no basta para acreditar destinos.
- **Finalización:** al menos webhook + router/filtro + dos destinos y evidencia de recepción de ETL real; exportación/capturas sin secretos; riesgos de duplicar email y reintentos documentados. Si faltan acceso/autorización externa, F10 sigue pendiente y no se declara entrega completa.
- **Commits sugeridos:** `feat: deliver persisted ETL summaries to Make`; `docs: add sanitized Make blueprint and execution evidence`.
- **Rama / PR:** `feature/make-integration`, PR 5 a `main`.
- **Dependencias:** F9 integrado (consultas requeridas proceden de F8); acceso real a Make y destinos.

## F11 — Robustez opcional

- **Objetivo:** mejorar solo después de satisfacer requisitos obligatorios.
- **Tareas:** elegir extras con beneficio: incremental `updated_since` con watermark/solapamiento y refresco completo, métricas de retries y presupuesto de tiempo, logging enriquecido, contenedores para ETL/web, comparativa YoY con meses comparables y ausencia de histórico visible. No rehacer arquitectura ni posponer aquí retry/logging básicos.
- **Archivos previstos:** cliente/repositorio/config, tests correspondientes, `Dockerfile` y cambios autorizados de Compose, `queries.py`/web si YoY, SOLUCION.
- **Tests:** incremental vacío mantiene stock, límite inclusivo no duplica, fallo no avanza watermark, eliminación solo detectable en refresco completo; arranque de contenedores; YoY sin base previa produce NULL, no crecimiento inventado. Ejecutar únicamente los aplicables a extras elegidos.
- **Finalización:** cada extra elegido tiene evidencia y no degrada F0–F10; lo no elegido queda fuera explícitamente. No es necesario implementar todos para cerrar entrega obligatoria.
- **Commits sugeridos:** `feat: add safe incremental stock refresh`; `chore: containerize ETL and web services` (solo si se hacen).
- **Rama / PR:** `feature/optional-hardening`, PR 6 opcional; dividir por extra si crece.
- **Dependencias:** F10 cerrado.

## F12 — Documentación y entrega

- **Objetivo:** repositorio reproducible, evidencias auténticas y entrega revisable.
- **Tareas:** completar SOLUCION; validar arranque desde clon limpio y BD de pruebas nueva sin borrar volumen del usuario; ETL dos veces con entradas controladas; tests/lint configurado; dashboard y Make; revisar secretos en cambios, historial relevante, blueprint y capturas; `.gitignore`; verificar ≥3 ramas, ≥2 PR y main funcional. Preparar una demostración breve y reproducible que siga un registro desde la fuente hasta el rechazo o la métrica, y localizar los módulos que habría que cambiar ante una nueva columna, una paginación distinta o un nuevo desglose del gráfico. Explicar cinco millones de líneas, limitaciones, exclusiones y uso de IA. Preparar borrador de correo y enlaces/acceso, sin enviarlo automáticamente.
- **Archivos previstos:** `SOLUCION.md`, documentación ajustada a implementación real, evidencias en `docs/` y `make/capturas/`, `.gitignore` si necesario; no adjuntar `.env` ni dumps con clientes.
- **Tests/verificación:** repetir procedimiento documentado, comparar negocio tras segunda pasada y confirmar nuevos runs de auditoría; ejecutar suite completa una vez tras cambios finales; comprobar UI y historial Make; verificar enlaces y PR reales en GitHub. Una limitación pendiente de Make no equivale a éxito.
- **Finalización:** A01–A11 acreditados; cero TBD críticos de ejecución obligatoria; lo opcional no realizado identificado; main contiene versión reproducible; paquete de correo listo. Su envío requiere instrucción explícita del usuario y queda fuera del cierre técnico automático.
- **Commits sugeridos:** `docs: finalize reproducible setup and delivery evidence`; `chore: exclude local artifacts from version control` si procede.
- **Rama / PR:** `feature/delivery-docs`, PR final a `main`.
- **Dependencias:** F10; F11 solo si se eligió e integró.

## Estrategia Git y PR

No crear ahora las ramas ni commits futuros. La rama actual observada es `main`; hay un cambio previo en `.gitignore` que no debe incorporarse por accidente. La planificación puede entregarse en una rama documental propia en una tarea de Git posterior; no cuenta como sustituto de ramas funcionales.

| PR previsto | Rama nacida del main actualizado | Fases y resultado revisable |
| --- | --- | --- |
| 1 | `feature/etl-products` | F0–F4: catálogo y tarifas con MySQL/auditoría y pruebas. Abrir borrador temprano; incorporar commits por fase, sin esperar a todo el proyecto. |
| 2 | `feature/etl-stock` | F5: cliente y consolidación de stock con fallos controlados. |
| 3 | `feature/orders` | F6–F7: cuatro fuentes relacionadas, pruebas E2E e idempotencia. |
| 4 | `feature/dashboard` | F8–F9: SQL validado y panel completo. |
| 5 | `feature/make-integration` | F10: integración real y artefactos Make. |
| 6 opcional | `feature/optional-hardening` | F11: extras seleccionados. |
| Final | `feature/delivery-docs` | F12: guía y evidencias finales. |

La estrategia supera naturalmente tres ramas y dos PR sin acumular el proyecto en una sola. Cada rama empieza tras integrar sus dependencias a `main`; evitar ramas apiladas innecesarias. `main` debe pasar las verificaciones de su incremento y la entrega final debe cumplir todo lo obligatorio. No fusionar scripts a medio funcionar ni afirmar que un incremento parcial ya cumple el ejercicio.

Commits pequeños por cambio coherente (una regla junto con sus tests, un script de esquema, una consulta o documentación). Describir problema, comportamiento resultante, decisiones y verificación real en cada PR; enlazar fase/requisitos y limitar el diff. Preservar commits descriptivos al integrar cuando aporten información; no fabricar historial ni PR después del trabajo para simular proceso. Verificar PR merged hacia main y conservar evidencia/enlaces aunque se eliminen ramas remotas.

Antes de cada merge: tests de la fase y regresiones afectadas, diff/secretos revisados, documentación consistente, sin ficheros originales de datos alterados. No ejecutar `git add .` con cambios ajenos. La creación/publicación de PR se hará cuando se solicite trabajo Git y exista remoto/acceso, no como efecto de esta planificación.

## Cómo pedir trabajo a una IA

Ejemplo de solicitud futura: «Implementa únicamente F1 siguiendo AGENTS y los documentos de planificación. Antes del cambio identifica archivos, razón y criterio; prueba las reglas y resume evidencias y pendientes. No avances a F2». Una fase puede dividirse en tareas aún más pequeñas si no cabe en un diff revisable.

El siguiente paso es revisar e integrar PR 2 de F5. Después podrá solicitarse F6 por separado. Resolver cada supuesto en su fase y dejar documentada la decisión si no hay confirmación comercial; nunca rellenar huecos con datos inventados.
