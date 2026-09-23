# Solución — documento vivo

**Estado: plantilla de entrega. Solo se ha realizado planificación documental.** No existen todavía resultados de ETL, tests funcionales, dashboard o Make aportados por esta tarea. `TBD` significa pendiente de implementación/verificación; no sustituirlo por estimaciones presentadas como hechos.

Diseño propuesto: [PRD](PRD.md), [TECH_SPEC](TECH_SPEC.md), [DATA_RULES](DATA_RULES.md), [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md), [ADR](docs/adr/README.md). Al finalizar, actualizar esta guía a lo realmente implementado y distinguirlo de propuestas descartadas.

## Resumen

- Problema: consolidar catálogo CSV, tarifas XML, pedidos CSV y stock REST del distribuidor B2B.
- Funcionalidad realmente implementada: **TBD**.
- Versión/commit entregado y enlace GitHub: **TBD**.
- Estado de requisitos obligatorios y extras: **TBD**.

## Arquitectura final

TBD: incluir diagrama real y tecnologías/versiones verificadas. Propuesta inicial: Python → MySQL 8; FastAPI/HTML/Chart.js para consulta; resumen posterior al commit → Make → email e histórico. No declarar esta arquitectura implementada hasta comprobarla.

## Requisitos de entorno

- Docker/Compose: necesarios según README; versiones verificadas **TBD**.
- Python y dependencias fijadas: **TBD** (3.12 es propuesta).
- Puertos/servicios del entorno provisto: MySQL host 3307, API stock 3001; disponibilidad real **TBD**.
- Acceso a Make y cuentas de destino: **TBD**, sin incluir tokens/credenciales.
- Configuración de zona horaria, moneda y base fiscal: **TBD**.

## Cómo levantar desde cero

Checklist que debe convertirse en procedimiento probado en F12:

1. Clonar repositorio y seleccionar versión de entrega: URL/commit **TBD**.
2. Preparar `.env` a partir de `.env.example` solo si no existe. Mantenerlo local. Variables nuevas y valores no secretos: **TBD**. No mostrar claves reales en ejemplos.
3. Comprobar que variables de la aplicación coinciden con servicios: Compose tiene valores demo literales y no interpola automáticamente todo `.env`.
4. El README proporciona `docker compose up -d` para MySQL/API; ejecución verificada aquí **TBD**. Comprobar healthchecks y `/health`, luego una página de stock autenticada con token desde entorno sin imprimirlo. Salida real saneada **TBD**.
5. Crear entorno Python e instalar dependencias fijadas: comandos reales **TBD**.
6. Aplicar scripts versionados de BD: comando y orden **TBD**. `db/init` solo se ejecuta al inicializar volumen; no borrar volúmenes existentes para aplicar actualizaciones.
7. Arrancar web: comando, host/puerto y URL local **TBD**.
8. Registrar validación desde clon/BD de pruebas nuevos, fecha y commit: **TBD**. No ejecutar pruebas destructivas sobre el volumen del usuario.

No se ofrece todavía una secuencia completa ejecutable: falta implementar la aplicación y verificarla. En F12 no pueden quedar pasos críticos implícitos.

## Cómo ejecutar el ETL

- Comando real y opciones: **TBD**. Interfaz propuesta: `python -m src.etl`; aún no existe por esta planificación.
- Variables/rutas de las cuatro fuentes: **TBD**.
- Códigos de salida y significado de ejecución fallida/con rechazos/notificación fallida: **TBD**.
- Procedimiento de repetición con las mismas entradas: **TBD**.
- Reenvío a Make de un run confirmado sin repetir ETL: **TBD**.
- Recuperación tras fallo/concurrencia: **TBD**.

## Cómo ejecutar tests

Comandos unitarios, integración MySQL y lint/format configurados: **TBD**. pytest es propuesta, no resultado ejecutado. Documentar creación de BD de pruebas aislada y variables requeridas sin secretos. No usar la BD del usuario para tests que eliminen datos.

## Esquema de base de datos

DDL aplicado y diagrama final: **TBD**. Propuesta conceptual: products, orders, order_lines, stock_by_warehouse, etl_runs y rejections. Justificación de PK/FK/UNIQUE/índices: [TECH_SPEC](TECH_SPEC.md). Incluir versiones de scripts realmente aplicadas y controles de integridad: **TBD**.

## Decisiones sobre calidad de datos

Reglas propuestas en [DATA_RULES](DATA_RULES.md): encoding por fuente, nulos, precios Decimal, EAN conservador, selección determinista de duplicados, descuentos, fechas, estados/canales y stock desconocido. Reglas realmente implantadas y diferencias justificadas: **TBD**. Descartes observados e impacto: **TBD**.

## Definición de facturación y margen

Propuesta: ENVIADO/COMPLETADO con líneas válidas positivas, excluyendo cancelados, pendientes y devueltos; importe tras descuento de línea. Coste actual disponible para margen y cobertura visible cuando falta coste. No se conoce aún la base fiscal confirmada de los precios.

Decisión final, validación EUR/IVA, tratamiento de devoluciones, fecha de referencia, zona horaria y ejemplo real conciliado: **TBD**. Explicar pedidos parciales y desconocidos. No afirmar rentabilidad histórica exacta con costes actuales.

## Productos históricos

Propuesta: productos mínimos por SKU para mantener FKs, sin inventar coste/stock, excluidos del catálogo comercial y presentes en ventas. Implementación y evidencia de promoción cuando vuelve un SKU: **TBD**. Conteos e impacto sobre cobertura de margen: **TBD**.

## Idempotencia

Propuesta: claves únicas, upserts y reconciliación de instantáneas con firma de línea; auditoría por run. Confirmación de que CSV es completo y política sobre dos líneas legítimas idénticas: **TBD**.

Evidencia requerida: mismas entradas y versión de reglas en dos runs; comparación de contenido/conteos de negocio, FKs y stock; timestamps/metadatos excluidos; incremento esperado de auditoría. Identificadores de run y resultados: **TBD**. Prueba de corrección de línea y rollback: **TBD**.

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
| Fecha/commit/reglas y entorno | TBD |
| Hashes de entrada y fecha de referencia | TBD |
| run_id inicial / repetición y estados | TBD |
| Registros leídos por fuente | TBD |
| Productos aceptados/insertados/actualizados/sin cambio | TBD |
| Productos históricos | TBD |
| Pedidos/líneas aceptados y pedidos parciales | TBD |
| Stock por almacén y productos con stock desconocido/inválido | TBD |
| Filas leídas/aceptadas/rechazadas/deduplicadas por fuente; avisos y campos descartados aparte | TBD |
| Facturación, unidades, ticket y margen/cobertura | TBD |
| Duraciones y estado Make | TBD |
| Comparación de datos de negocio entre runs | TBD |

## Rechazos

Consultas para revisar fuente/localizador/motivo y ejemplos saneados: **TBD**. Distribución real por reason_code y acción: **TBD**. Verificar `rows_read = rows_accepted + rows_rejected + rows_deduplicated` por fuente completa; los duplicados no cuentan como rechazos. Avisos y campos descartados se informan aparte. Una fila con varios motivos cuenta una vez como rechazada, pero puede aportar varios motivos. Reconciliación real de contadores: **TBD**.

## Pruebas realizadas

| Verificación | Comando / evidencia | Resultado |
| --- | --- | --- |
| Unitarias de normalización y pricing | TBD | TBD |
| API mock, paginación y errores | TBD | TBD |
| MySQL, FKs y rollback | TBD | TBD |
| ETL completo y segunda ejecución | TBD | TBD |
| SQL/conciliación de métricas | TBD | TBD |
| Web en navegador | TBD | TBD |
| Make con ejecución real y destinos | TBD | TBD |
| Arranque desde cero y secretos | TBD | TBD |

La revisión de planificación no equivale a ejecutar estas pruebas funcionales. No registrar «todos los tests pasan» hasta disponer de comandos y resultados reales.

## Qué cambiaría con cinco millones de líneas

Propuesta de evolución, pendiente de contrastar mediante medidas: lectura en streaming y staging MySQL por lotes, validación/deduplicación con índices y conjuntos en BD en vez de todo en memoria; publicación de versión consolidada solo tras validar; upserts/reconciliación por particiones o versión de snapshot; ID estable de línea del ERP para incrementar con seguridad. Medir EXPLAIN/índices y preagregar meses si las consultas lo necesitan. Definir retención/acceso de payloads e historial, backups y recuperación. Stock incremental con watermark y refresco completo periódico por falta de tombstones.

No introducir Spark/Kafka/Kubernetes solo por el número de filas: medir memoria, duración y cuellos antes. Decisiones finales, benchmark o estimaciones identificadas como tales: **TBD**.

## Limitaciones

Por validar: ausencia de ID de línea y coste histórico; base fiscal/zona de negocio; política de devoluciones; stock por instantánea y antigüedad; entrega Make al menos una vez. Limitaciones realmente encontradas, impacto y mitigación: **TBD**.

## Cosas dejadas fuera por tiempo

**TBD**: registrar lo realmente omitido. Candidatos opcionales: incremental, dockerización completa, YoY y mejoras operativas. No etiquetar un requisito obligatorio incumplido como «opcional»; indicarlo de forma explícita si finalmente falta.

## Uso de IA

Se usó Codex para inspeccionar el repositorio y redactar esta planificación. No se implementó el ETL ni se ejecutaron pruebas funcionales en esa tarea. El responsable deberá revisar y poder explicar las decisiones propuestas.

Uso durante implementación, tareas asistidas, decisiones revisadas personalmente, validación y errores detectados: **TBD**. No atribuir aprobaciones o verificaciones humanas que no han ocurrido.

## Entrega y Git

- Enlace GitHub y acceso si privado: **TBD**.
- Ramas reales (mínimo tres de trabajo) y enlaces de PR merged a main (mínimo dos): **TBD**.
- Commit de main verificado y procedimiento reproducible: **TBD**.
- Resumen de dos o tres párrafos: **TBD**.
- Captura de panel con gráfico, escenario Make y ejecución correcta: **TBD**.
- Borrador de correo conforme al destinatario/asunto de README: **TBD**. Preparar no equivale a enviar; no se envía automáticamente.
