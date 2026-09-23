# Solución — documento vivo

**Estado: plantilla de entrega. F0 de entorno comprobada; ETL, tests de negocio, dashboard y Make pendientes.** `TBD` significa pendiente de implementación/verificación; no sustituirlo por estimaciones presentadas como hechos.

Diseño propuesto: [PRD](PRD.md), [TECH_SPEC](TECH_SPEC.md), [DATA_RULES](DATA_RULES.md), [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md), [ADR](docs/adr/README.md). Al finalizar, actualizar esta guía a lo realmente implementado y distinguirlo de propuestas descartadas.

## Resumen

- Problema: consolidar catálogo CSV, tarifas XML, pedidos CSV y stock REST del distribuidor B2B.
- Funcionalidad realmente implementada: bootstrap de dependencias, configuración de pytest/Ruff y comprobación local de servicios (F0). Lógica de integración: **TBD**.
- Versión/commit entregado y enlace GitHub: **TBD**.
- Estado de requisitos obligatorios y extras: **TBD**.

## Arquitectura final

TBD: incluir diagrama real y tecnologías/versiones verificadas. Propuesta inicial: Python → MySQL 8; FastAPI/HTML/Chart.js para consulta; resumen posterior al commit → Make → email e histórico. No declarar esta arquitectura implementada hasta comprobarla.

## Requisitos de entorno

- Entorno local comprobado en F0 (23/09/2026): Python 3.13.13, Docker 29.2.1 y Compose 2.38.2. MySQL respondió como 8.0.46. Se usa 3.13 porque la versión 3.12 propuesta no está disponible en este equipo; compatibilidad con otros Python **TBD**.
- Dependencias resueltas y fijadas en `requirements.txt`; configuración de pytest y Ruff en `pyproject.toml`. La justificación de dependencias está más abajo. Instalación en otro equipo **TBD**.
- Puertos/servicios del entorno provisto: MySQL host 3307 y API stock 3001; ambos estaban `healthy` en F0. Esta observación local no sustituye la comprobación desde cero de F12.
- Make y los dos destinos: no hay `MAKE_WEBHOOK_URL` ni destinatario de alerta en `.env` local; acceso/conexiones reales **TBD** para F10. El token local se usó en memoria para la comprobación autenticada; no se mostró ni publicó.
- GitHub: `origin` está configurado y un `git push --dry-run` a `feature/etl-products` terminó correctamente; no se publicó esa rama por esta comprobación. La accesibilidad final del repositorio entregado se verificará en F12.
- Configuración de zona horaria, moneda y base fiscal: **TBD**.

## Cómo levantar desde cero

Pasos de bootstrap comprobados en F0, que F12 debe repetir desde un clon limpio:

1. Clonar repositorio y seleccionar versión de entrega: URL/commit **TBD**.
2. Preparar `.env` a partir de `.env.example` solo si no existe. En F0 ya existía y se conservó. Mantenerlo local; no mostrar claves reales en ejemplos. Variables nuevas para la aplicación futura: **TBD**.
3. Comprobar que variables de la aplicación coinciden con servicios: Compose tiene valores demo literales y no interpola automáticamente todo `.env`. La conexión local de F0 confirmó que los valores actuales coinciden.
4. El README proporciona `docker compose up -d` para MySQL/API. Después, comprobar `docker compose ps` y `curl --fail http://localhost:3001/health`. En F0 los servicios ya estaban en marcha: se comprobó `docker compose ps`, `/health` y una página autenticada, sin reiniciarlos ni imprimir el token. Se observó `/health` 200, 401 sin token y 200 con token (`data`: 5 elementos, `meta`: `page`, `per_page`, `total_records`, `total_pages`, `has_next`). El token se leyó desde `.env` mediante `python-dotenv` en memoria, no se pasó como literal de línea de comandos.
5. Crear el entorno Python e instalar dependencias fijadas:

   ```bash
   python3.13 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   .venv/bin/python -m pip check
   ```

   En F0 se creó `.venv` local y se instalaron las versiones fijadas. La verificación de instalación desde `requirements.txt` y `pip check` consta en las pruebas realizadas. `.venv` y las cachés de herramientas están ignoradas por Git.
6. Aplicar scripts versionados de BD: comando y orden **TBD**. `db/init` solo se ejecuta al inicializar volumen; no borrar volúmenes existentes para aplicar actualizaciones.
7. Arrancar web: comando, host/puerto y URL local **TBD**.
8. Registrar validación desde clon/BD de pruebas nuevos, fecha y commit: **TBD**. No ejecutar pruebas destructivas sobre el volumen del usuario.

El entorno base responde, pero aún no hay ETL, esquema ni web: no se ofrece todavía una secuencia completa ejecutable. En F12 no pueden quedar pasos críticos implícitos.

### Dependencias elegidas en F0

`PyMySQL` proporciona el driver de MySQL que falta en la biblioteca estándar; `httpx` sirve tanto para la API como para el webhook y permite simular transporte en tests. `FastAPI`, `Uvicorn` y `Jinja2` sostendrán la página HTML propuesta, sin SPA ni ORM. `python-dotenv` permite cargar `.env` local sin ejecutarlo como shell ni sobrescribir variables; `pytest` verifica reglas futuras y `Ruff` configura un lint ligero. No se añade pandas, un segundo cliente HTTP ni un framework de migraciones. El uso de estas dependencias por módulos de aplicación queda pendiente de sus fases; F0 solo valida instalación/importación.

## Cómo ejecutar el ETL

- Comando real y opciones: **TBD**. Interfaz propuesta: `python -m src.etl`; aún no existe por esta planificación.
- Variables/rutas de las cuatro fuentes: **TBD**.
- Códigos de salida y significado de ejecución fallida/con rechazos/notificación fallida: **TBD**.
- Procedimiento de repetición con las mismas entradas: **TBD**.
- Reenvío a Make de un run confirmado sin repetir ETL: **TBD**.
- Recuperación tras fallo/concurrencia: **TBD**.

## Cómo ejecutar tests

pytest y Ruff quedaron instalados y configurados en F0; todavía no existe código de negocio ni tests del proyecto que ejecutar. Comandos concretos de unitarias e integración MySQL: **TBD** en sus fases. Documentar creación de BD de pruebas aislada y variables requeridas sin secretos. No usar la BD del usuario para tests que eliminen datos.

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
| F0: versiones y dependencias | `python3.13 --version`, `docker --version`, `docker compose version`, `pip install -r requirements.txt`, `pip check`, importación de 8 dependencias directas | Python 3.13.13; Docker 29.2.1; Compose 2.38.2; instalación/importaciones correctas; `pip check`: sin incompatibilidades. |
| F0: servicios y credenciales locales | `docker compose ps`; `/health`; GET stock sin/con Bearer leído de `.env`; conexión MySQL con PyMySQL | Ambos contenedores healthy; health 200; stock 401 sin token y 200 con token, 5 registros; MySQL 8.0.46/base `catalogo`, 0 tablas. |
| F0: remoto Git | `git push --dry-run origin HEAD:refs/heads/feature/etl-products` | Éxito; no se subieron cambios. |
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
