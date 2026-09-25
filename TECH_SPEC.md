# Especificación técnica propuesta

Estado: ETL implementado hasta F6 y validado end-to-end en F7; consultas SQL analíticas implementadas y verificadas en F8. Web y Make siguen siendo diseño pendiente. R/D/S se definen en [PRD.md](PRD.md). Las reglas concretas pertenecen a [DATA_RULES.md](DATA_RULES.md); el orden de trabajo a [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). La inspección siguiente describe el estado inicial; la evidencia actual está en [SOLUCION.md](SOLUCION.md).

## Inspección y límites de evidencia

Se leyeron README, `.env.example`, Compose, `make/README.md`, XML y código de la API simulada. Se inspeccionaron cabeceras y pequeñas muestras CSV/stock; se recorrieron exclusivamente las columnas estado/canal para obtener sus valores distintos, y se buscaron unos pocos ejemplos de anomalías. No es un perfil estadístico completo ni una ejecución ETL. No se leyó `.env`.

El repositorio tiene `data/`, `mock-api/`, `db/init/.gitkeep` y `make/README.md`, sin esquema ni aplicación de la solución. `.gitignore` ya tenía un cambio del usuario. Compose levanta MySQL 8.0 (host 3307, contenedor 3306) y API Node (3001), con healthchecks; solo esos servicios están dockerizados. La API simulada escribe su token en el arranque: no copiar esos logs a evidencias ni reproducir ese patrón en la aplicación.

El XML contiene `PorcentajeBase`, `PorVolumen`, portes y plazo de pago, además de excepciones. La muestra de stock contiene `sku`, `warehouse`, `quantity`, `reserved`, `updated_at`. Pedidos no trae ID de línea; la fecha de una misma cabecera puede venir como día o con hora. Se observó una devolución con cantidad positiva, por lo que no se puede interpretar todo DEVUELTO como ajuste negativo.

## Arquitectura general (D)

```text
CSV catálogo ─┐
XML tarifas ──┼─> extracción -> normalización -> validación -> lote validado
CSV pedidos ──┤                                                   │
API stock ────┘                                          transacción MySQL
                                                                  │
                                   ┌──────────────────────────────┴─────┐
                                   ↓                                    ↓
                          SQL -> FastAPI/HTML                  resumen ETL confirmado
                               + Chart.js                         -> webhook Make
                                                                        │
                                                             router -> email / Sheets
```

Un único proyecto Python, un comando ETL síncrono y una aplicación web de lectura, compartiendo configuración y consultas. Extraer y validar antes de abrir la transacción de negocio; no mantener una transacción abierta durante peticiones HTTP. Un fallo fatal deja la versión anterior publicada. Las filas inválidas se descartan según reglas y pueden producir una ejecución `success_with_rejections`. Una extracción incompleta nunca se publica.

Tecnologías propuestas, a fijar y probar en F0:

| Elección | Justificación y alternativa |
| --- | --- |
| Python 3.13, `csv`, `xml.etree.ElementTree`, `decimal`, `datetime`, `logging` | Biblioteca estándar para el volumen local; evitar pandas y conversiones implícitas a float. F0 validó Python 3.13.13 en el host; 3.12 no está instalado aquí. |
| MySQL 8 y Compose existentes | Requisito y entorno del ejercicio. No sustituir por SQLite para verificar restricciones. |
| FastAPI + Uvicorn + Jinja2 | Una ruta HTML, validación de filtros y posible JSON; Flask sería igualmente suficiente y requiere menos piezas de tipado. Se elige FastAPI por validación explícita y facilidad de pruebas. |
| HTML simple + Chart.js | Un gráfico y tablas sin SPA, bundler ni frontend Node. Fijar versión del recurso y documentar acceso a CDN o incluir copia local. |
| PyMySQL, SQL parametrizado | Un driver y SQL visible, sin ORM ni framework de migración para unas pocas tablas. SQLAlchemy es alternativa si el modelo crece. Scripts SQL versionados bastan inicialmente. |
| `httpx` síncrono | Un cliente para stock y webhook, timeouts y transporte simulable en tests. `requests` sería válido, no instalar ambos. |
| pytest | Fixtures pequeñas y pruebas de negocio, más integración contra MySQL de pruebas separado. |
| python-dotenv | Opcional en F0 para cargar `.env` local sin sobrescribir el entorno; si se adopta se justificará y fijará. También es válido inyectar variables desde el shell. |

No hacen falta colas ni procesos distribuidos. El diseño no depende de Kafka, Spark, Airflow, Kubernetes o microservicios. Las consultas son de solo lectura; no añadir endpoints de ejecución ETL sin necesidad.

## Estructura propuesta

```text
src/
  __init__.py
  config.py                 # entorno, validación y valores configurables
  db.py                     # conexión y transacciones; sin reglas de negocio
  etl/
    __init__.py
    __main__.py             # comando previsto python -m src.etl
    runner.py               # ciclo de ejecución y publicación atómica
    records.py              # contratos tipados y procedencia
    normalize.py            # funciones puras de strings/fechas/números/EAN
    catalog.py              # CSV, validación y selección por SKU
    pricing.py              # XML y coste neto
    stock_client.py         # transporte, páginas y reintentos
    stock.py                # almacenes y consolidación
    orders.py               # cabeceras, líneas e identidad
    repository.py           # carga parametrizada y reconciliación
    reporting.py            # contadores y resumen de ejecución
    make_client.py          # envío posterior al commit, sin secretos en logs
  analytics/
    queries.py              # SQL revisado y definiciones únicas de métricas
  web/
    app.py                  # filtros y renderizado, sin lógica ETL
    templates/index.html
    static/                 # JS/CSS mínimos
db/
  migrations/               # SQL versionado e instrucciones de aplicación
  init/                     # montaje existente; no es mecanismo de actualización
tests/
  unit/
  integration/
  fixtures/                 # muestras sintéticas pequeñas, claramente marcadas
make/
  escenario.blueprint.json  # solo después de exportarlo realmente
  capturas/
docs/adr/
pyproject.toml              # dependencias, pytest y lint si se configura
```

Interfaces conceptuales: un registro extraído contiene fuente, localizador y payload; la normalización produce entidad válida e incidencias; el repositorio recibe el lote ya validado. No escribir esos módulos en la tarea de planificación.

## Modelo conceptual

Usar InnoDB, `utf8mb4`, identificadores canónicos y colación binaria en claves naturales normalizadas. Tamaños propuestos: SKU 64, pedido 64, almacén 64; validar límites, nunca truncar. `BIGINT` para IDs internos y cantidades, `DATE` para día de pedido, `DATETIME(6)` en UTC para auditoría/API, `DECIMAL(18,4)` para precios unitarios y `DECIMAL(9,6)` para ratios; totales calculados a dos decimales. No es DDL definitivo.

| Tabla | Propósito / PK | FK y UNIQUE | Campos e índices relevantes |
| --- | --- | --- | --- |
| `products` | Catálogo y referencias históricas; PK `id` | UNIQUE `sku`; `last_run_id` → `etl_runs.id` | SKU no nulo, EAN nullable (no único), nombre, marca/categoría y claves de cruce, coste base/neto, PVP, IVA ratio, peso, alta, descripción; `is_historical`, `in_catalog`, `stock_total` nullable, `stock_status`, procedencia de precio y `stock_as_of`. Índice categoría. Costes/PVP nulos permitidos solo para históricos; no inventar cero. |
| `orders` | Una cabecera aceptada por pedido; PK `id` | UNIQUE `source_order_id`; `last_run_id` → `etl_runs.id` | Día, cliente nullable, canal, estado y `has_rejected_lines`. Índice `(status, order_date)` y canal/fecha si EXPLAIN lo justifica. |
| `order_lines` | Líneas aceptadas; PK `id` | `order_id` → orders, `product_id` → products, `last_run_id` → etl_runs; UNIQUE `(order_id, line_key)` | `line_key CHAR(64)` SHA-256, cantidad firmada, precio unitario, descuento ratio, localizador fuente. Índice `(product_id, order_id)`; FKs RESTRICT y borrado explícito de líneas al reconciliar. |
| `stock_by_warehouse` | Última observación aceptada por almacén; PK `(product_id, warehouse_code)` | product → products; last_run → etl_runs | quantity, reserved, updated_at; no sumar dos versiones del mismo almacén. Índice actualización solo si incremental lo necesita. Se propone esta tabla para auditar la suma exigida en products. |
| `etl_runs` | Registro de cada intento; PK UUID `id` | Sin clave natural de negocio | Inicio/fin UTC, estado, fase/error resumido, hashes de CSV/XML y respuesta de stock ordenada, versión de reglas/config no secreta, contadores JSON, fecha de referencia analítica, `make_status`, intentos de entrega y resumen JSON. Índice inicio/estado. |
| `rejections` | Descartes de fila/campo y avisos de calidad; PK `id` | `run_id` → etl_runs; UNIQUE `(run_id, source, record_locator, reason_code, field_name)` | `field_name` no nulo, vacío para fila completa; entidad, severidad, acción, detalle y payload JSON/texto limitado. Índice `(run_id, reason_code)` y `(source, entity_key)`. No FK a producto/pedido: la entidad puede haber sido rechazada. |

Las restricciones de BD incluyen dominios válidos, rangos de descuentos y cantidades/precios coherentes con el estado. Las reglas que requieren JOIN o comparar varias filas se validan antes de cargar y mediante consultas de control: no prometer CHECKs entre tablas. Claves, FKs y rangos locales se verifican también en MySQL, no solo en Python.

No se propone tabla de clientes ni catálogo de marcas/categorías: textos canónicos son suficientes. Las reglas de tarifa y su origen se conservan en el precio/procedencia del producto y en el hash de XML del run; no es necesario un subsistema temporal de tarifas.

## Integridad referencial e históricos

D: para un SKU de una línea histórica válida que falte en el catálogo aceptado, crear/reutilizar un producto mínimo `is_historical=true`, `in_catalog=false`, coste/PVP/EAN/stock nulos y nombre de presentación «SKU … (histórico)». Es una etiqueta de interfaz, no un nombre atribuido al proveedor. Registrar `HISTORICAL_PRODUCT_CREATED` solo al crear el producto; distinguir en el detalle ausencia original de catálogo frente a producto rechazado. Reutilizar el ID existente no repite ese evento. No crear históricos a partir de líneas rechazadas.

Si posteriormente aparece en catálogo, actualizar el mismo ID y quitar el indicador histórico. Los productos que dejan de estar en la instantánea se conservan para FKs, pasan a históricos y pierden coste/stock actuales; no presentar el valor previo como vigente. La auditoría conserva procedencia y motivo del cambio, pero un hash de fuente no permite reconstruir sus valores: sin conservar el fichero de aquella ejecución no existe historial completo de precios. Ocultarlos por defecto del listado comercial, pero incluirlos en análisis de ventas bajo «Sin categoría» cuando proceda.

Alternativas: rechazar líneas pierde facturación; FK nullable rompe la relación exigida; un único producto «desconocido» mezcla SKUs. La propuesta conserva identidad sin inventar atributos. Margen desconocido queda excluido del subtotal de margen conocido, con cobertura visible. Véase ADR 003.

## Idempotencia y transacciones

D: modo inicial de **instantáneas completas** de CSV/XML/stock, una sola ejecución concurrente permitida (bloqueo de proceso o advisory lock MySQL con liberación garantizada). Los hashes identifican entradas, no evitan por sí solos cargar datos.

1. Crear `etl_runs` durable; extraer todas las páginas y ficheros, normalizar y preparar el lote. Guardar incidencias aun si falla el run, en transacción de auditoría separada.
2. En una única transacción de negocio: upsert por SKU/pedido, resolver históricos, sincronizar líneas, reemplazar conjunto de stock de la instantánea y actualizar totales/estado de productos. Los IDs existentes se conservan mediante upsert.
3. Reconciliar líneas ausentes de cada pedido y pedidos ausentes del conjunto aceptado; eliminar primero líneas, luego cabeceras sin líneas. No usar TRUNCATE ni desactivar FKs. Marcar productos no vigentes, no borrarlos. Un pedido completamente inválido no conserva silenciosamente su versión de un run anterior: se retira de la vista de negocio y queda auditado. Si el fichero está inesperadamente vacío, falla estructuralmente o no tiene ninguna entidad válida, abortar antes de reconciliar y exigir revisión.
4. Confirmar datos y estado/resumen del run conjuntamente. Si falla MySQL, rollback de negocio y marcar run failed aparte. Una caída abrupta deja la transacción de negocio sin publicar; el run incompleto se revisa manualmente antes de repetir.
5. Enviar a Make después del commit. El envío fallido no revierte datos ni provoca otro ETL automático.

Identidad de línea: hash de serialización canónica versionada de `(id_pedido, sku, cantidad, precio_unitario, descuento_linea)`; sin número físico de fila ni campos redundantes de cabecera. Una línea modificada cambia de hash y la reconciliación elimina la anterior. Colapsar líneas idénticas es una decisión provisional: no hay información que permita distinguir duplicado accidental de dos líneas legítimas idénticas; se audita y se declara esa limitación. La alternativa es conservar multiplicidad con índice de ocurrencia determinista; confirmar con el ERP antes de cambiar la política.

Dos ejecuciones con idénticas entradas y reglas dejan el mismo estado de negocio; auditoría, marcas temporales y notificaciones por ejecución pueden crecer. Para comparar se excluyen IDs de run, timestamps y metadatos de entrega. Tests usan stock congelado y fecha de referencia fija. Un cambio real de fuentes o de «hoy» puede cambiar métricas y no viola idempotencia. Véase ADR 002.

## Dinero, tarifas y métricas

`Decimal` desde texto hasta persistencia, `DECIMAL` en MySQL; en JSON cantidades monetarias se envían como strings decimales. Redondeo propuesto `ROUND_HALF_UP`: precio neto unitario a 4 decimales y cada importe/coste de línea a 2 antes de sumar. Nunca recalcular dinero en JS; Chart.js puede convertir valores ya calculados para dibujar, sin que esa conversión alimente KPIs.

D: usar el precio de la excepción XML válida cuando exista; en su ausencia, coste × (1 − descuento categoría − descuento marca). La suma debe ser menor que 1 para producir coste positivo. Alternativa secuencial: coste × (1−dc) × (1−dm); confirmar semántica antes de cambiar. No aplicar `PorVolumen` por faltar cantidad de compra ni portes/plazos al coste; no son requisitos y no se pueden deducir de cantidades vendidas. Reglas idénticas para la misma clave se deduplican; reglas contradictorias generan `CONFLICTING_TARIFF` y hacen fallar la ejecución antes de publicar un coste dudoso. XML ilegible o una regla general inválida también hacen fallar la ejecución.

D/S: facturación operativa incluye `ENVIADO` y `COMPLETADO`, con cantidades positivas; excluye pendientes, cancelados y devueltos. Conservar devueltos positivos/negativos para auditoría sin restarlos automáticamente: falta vínculo/fecha de devolución y podría restarse una venta no registrada. Alternativa futura: libro de ventas y abonos separado. «Facturación» no equivale a contabilidad fiscal. Confirmar si precios incluyen IVA; mientras no se valide, la interfaz debe advertir «base fiscal pendiente de confirmar».

Para una fecha de referencia `as_of` (por defecto hoy en `BUSINESS_TIMEZONE`), filtrar `2025-04-01 <= order_date <= as_of` y aplicar el mismo conjunto elegible en todas las consultas:

| Métrica | Definición propuesta y casos límite |
| --- | --- |
| Importe de línea | `round2(cantidad × precio_unitario × (1 − descuento_linea))`. No usar PVP para reconstruir ventas. |
| Facturación / pedidos / ticket | Suma de importes; COUNT DISTINCT de pedidos con al menos una línea aceptada elegible; cociente redondeado a 2, NULL si no hay pedidos. Pedidos parciales se incluyen solo por sus líneas aceptadas y se informa cuántos hay. |
| Evolución | Agrupar por año-mes y sumar importe/unidades firmadas elegibles (en la política inicial solo positivas). Completar todos los meses desde abril de 2025, con cero cuando no hay ventas, y etiquetar mes actual como parcial. |
| Canal / categoría | Misma base que facturación; categorías proceden del producto actual, histórico sin categoría en grupo explícito. Totales deben reconciliar con facturación. |
| Top 10 | Facturación por product_id/SKU descendente, desempate SKU ascendente; incluir histórico etiquetado. |
| Margen bruto conocido | Por línea con coste conocido: importe menos `round2(cantidad × products.net_cost)`. Sumar sin multiplicar ventas por joins a almacenes. Mostrar importe vendido con coste conocido / ventas totales como cobertura (NULL si total cero) y ventas de coste desconocido aparte. Es estimación a coste actual, no histórico. |
| Bajo stock | products.stock_total conocido < 5, producto vigente, y EXISTS línea elegible con cantidad > 0 en `[as_of menos 3 meses naturales, as_of]`. Restar meses conservando día o ajustando al último día válido. No sustituir NULL por 0. |
| Resumen Make | Facturación del mes natural anterior completo a `as_of`, bajo stock según la misma consulta, contadores del run. Si no hay ventas en ese mes, cero. |

Mantener SQL centralizado; el dashboard y Make consumen la misma definición. Evaluar estados y canal por cabecera evita dobles conteos. Unir stock agregado al producto, no multiplicar líneas por cada almacén.

## API de stock

Contrato leído del mock: GET `/health` sin autenticación; GET `/api/v1/stock` con Bearer desde entorno, `page` desde 1, `per_page` por defecto 50 y máximo 100. Respuesta `{data, meta}` con `page`, `per_page`, `total_records`, `total_pages`, `has_next`. `updated_since` filtra de forma inclusiva (`>=`). No se ha ejecutado ninguna petición para esta planificación.

D: cliente aislado y síncrono, timeout de conexión/lectura explícito (propuesta 5/15 s), hasta 5 intentos por página, backoff exponencial con jitter y límite (base 1 s, tope 30 s). Son parámetros de entorno. Reintentar 500 y errores transitorios de red; para 429 respetar `Retry-After` válido (segundos o HTTP-date) y esperar al menos ese plazo. Si excede el presupuesto total configurable, fallar de forma explícita en vez de ignorarlo. Sin cabecera válida, usar backoff. 401/403 y otros 4xx no recuperables fallan inmediatamente.

Regular peticiones secuencialmente bajo el límite conocido del mock (40/min; propuesta 30/min configurable, también para reintentos). Verificar metadatos, avance de páginas, tipos y respuesta no repetida; finalizar cuando `has_next=false`, incluyendo colección vacía. Incoherencia de meta, página incompleta que impide completar el contrato o agotamiento de intentos: run fallido, nada de publicar un stock parcial. Una fila inválida puede aislarse, marcando stock del SKU como desconocido según DATA_RULES.

El total físico usa `sum(quantity)` de un registro vigente por `(sku, warehouse)`; reservado se conserva aparte. Si `reserved > quantity`, registrar aviso y conservar ambos valores: su interpretación comercial está pendiente. No restar reserved sin decidir que se desea disponibilidad. Si no hay stock observado para un producto, total NULL. Una respuesta completa vacía implica stock desconocido para todos, no cero.

F11 puede añadir `updated_since`: persistir watermark solo tras commit, solapamiento por límite inclusivo y deduplicación por clave/fecha. El endpoint no publica tombstones de almacenes eliminados: mantener refresco completo periódico; una respuesta incremental vacía no borra lo anterior. No adelantar incremental a F5.

Concreción implementada en F5: el comando pasó a publicar catálogo, tarifas y stock; F6 incorporó pedidos. `002_stock.sql` añade `etl_runs.stock_sha256` y `stock_by_warehouse`; el migrador aplica versiones en orden y puede retomar el ADD COLUMN tras una interrupción sin perder datos. El hash de stock encadena las respuestas HTTP 200 completas en orden de página, precedidas de su longitud; identifica la entrada recibida, no un historial reconstruible ni una firma independiente de la paginación. El lock de F4 se conserva para que ambos incrementos no admitan escritores simultáneos.

Parámetros operativos de F5: `STOCK_PER_PAGE=50` (1–100), `STOCK_ATTEMPTS=5` (1–10), `STOCK_CONNECT_TIMEOUT=5` y `STOCK_READ_TIMEOUT=15` segundos (1–120), `STOCK_REQUESTS_PER_MINUTE=30` (1–40), `STOCK_BUDGET_SECONDS=300` (1–3600). Backoff base 1 segundo, jitter de 0 a 1 segundo y máximo 30; un `Retry-After` válido puede superar ese máximo, pero nunca el presupuesto restante. El presupuesto incluye descarga y esperas; se comprueba antes y después de cada petición y tras dormir. Los timeouts HTTP son por operación de red: no se promete interrupción exacta del proceso al segundo 300. No se siguen redirecciones ni se toman proxies del entorno para evitar reenviar el Bearer a otro destino. Se comprueban tamaño exacto de página, tipos y totales constantes. Los estados `known`/`unknown`/`invalid`, versiones descartadas y fecha agregada se concretan en DATA_RULES.

Concreción implementada en F6: `003_orders.sql` añade `orders`, `order_lines` y `etl_runs.orders_sha256`, con FKs, UNIQUE de pedido/firma de línea y restricciones de cantidades, precios, descuentos, estados y canales. `python -m src.etl` extrae y valida las cuatro fuentes antes de la transacción; publica pedidos y líneas junto con catálogo y stock. La reconciliación de snapshot elimina líneas/pedidos ausentes mediante `DELETE` parametrizado respetando las FKs. Los productos históricos se crean solo por líneas válidas cuyo SKU no tiene producto comercial; no se crean por filas rechazadas ni por stock desconocido. Los contadores de pedidos conservan la igualdad de filas y separan pedidos parciales, avisos e históricos creados. Corrección posterior a F7 (ADR 004): cliente se compara con `casefold()` tras normalizar NFC/espacios, conservando la primera etiqueta válida no vacía. Las diferencias reales de texto siguen rechazando la cabecera. Reglas `catalog-stock-orders-v2`; firma de línea sin cambios.

## Configuración y seguridad

Variables existentes: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `STOCK_API_URL`, `STOCK_API_TOKEN`, `CSV_PATH`, `XML_PATH`. Añadir en implementación `ORDERS_CSV_PATH`, `BUSINESS_TIMEZONE` (propuesta Europe/Madrid, S), `ANALYTICS_AS_OF` opcional, parámetros de HTTP/retries/límite, `LOG_LEVEL`, `WEB_HOST/PORT`, `MAKE_WEBHOOK_URL`, timeout Make y umbral de rechazos. Documentar valores no secretos en plantilla; no copiar credenciales de ejemplo a código. No cambiar `.env` existente sin necesidad ni mostrar su contenido.

El Compose actual tiene valores de demostración literales: no está configurado para sustituirlos todos desde `.env`. En F0 verificar alineación sin afirmar que cambiar `.env` cambia los contenedores; parametrización de Compose, si se necesita, sería cambio posterior explícito. Dentro de Docker los hosts serán nombres de servicio y MySQL puerto 3306, no localhost:3307. El volumen MySQL ya inicializado no vuelve a ejecutar `db/init`; aplicar scripts versionados sin borrar volúmenes.

Validar variables al arrancar, no registrar DSNs con contraseña ni URL completa del webhook. Logs: run_id, fase, fuente, motivo, conteos, duración y error saneado. Sin payloads completos de clientes en logs. Datos de prueba/real separados; prohibido TRUNCATE o `down -v` sobre el entorno del usuario.

## Make y entrega externa

D: resumen posterior al commit con `schema_version`, `run_id`, estado/fecha, productos válidos de catálogo presentes en el lote (no affected_rows de MySQL), `rows_read`, `rows_accepted`, `rows_rejected` y `rows_deduplicated` por fuente, `rejected_by_reason`, avisos y campos descartados por separado, facturación del último mes y lista/conteo de bajo stock. En una fuente completada, `rows_read = rows_accepted + rows_rejected + rows_deduplicated`; los avisos/campos descartados no se suman a esa igualdad. Mismo run_id al reintentar entrega; resumen guardado en etl_runs para reenviarlo sin repetir ETL.

Escenario: webhook -> validación/filtro -> router con ruta de histórico siempre a Google Sheets y ruta condicional de email si `rows_rejected > umbral` O existen productos bajo mínimos. `rows_deduplicated` no dispara por sí solo la alerta de calidad. Si no se cumple la condición solo corre histórico; ambas rutas corren cuando hay problema. Umbral absoluto entero configurable, inicialmente 0 como propuesta. No hacer las dos rutas mutuamente excluyentes dejando alertas sin histórico. Airtable es alternativa si no se dispone de Google.

Validar run_id en histórico para evitar filas duplicadas; documentar entrega al menos una vez y riesgo residual de email repetido si el destino falla después de enviarlo. HTTP 2xx del webhook solo confirma recepción; la captura del historial de Make debe verificar destinos. Timeout ambiguo: marcar entrega pendiente y permitir reenvío explícito con el mismo run_id. No prometer exactly-once. Fallo Make produce estado de notificación fallida visible y salida diferenciada, sin revertir la carga ya confirmada.

F10 requiere acceso del usuario a Make y conexiones de los destinos; no inventar tokens, blueprint ni capturas. El agente puede preparar código/configuración y el escenario, pero antes de enviar un email de prueba mediante herramientas debe existir una instrucción explícita de envío y destinatario. La futura ejecución real del ETL/escenario debe autorizarse con ese efecto conocido. La planificación actual no autoriza mensajes externos.

## Decisiones abiertas y puntos de validación

| Decisión propuesta | Alternativa | Validación / fase |
| --- | --- | --- |
| Descuentos aditivos | Secuenciales | Confirmar interpretación comercial en F3; tests fijarán fórmula. |
| Venta enviada/completada, sin devoluciones | Solo completada o abonos enlazados | Revisar con responsable y medir exclusiones reales en F6/F8. |
| Coste actual, base fiscal por confirmar | Coste histórico y normalización IVA si existen datos | No inventar fuentes; validar EUR/IVA y declarar límite en F8. |
| Deduplicación por firma y snapshot completo | Multiplicidad / ID de línea ERP | Validar contrato del histórico antes de F6. |
| Stock físico, sin reserva | Disponibilidad quantity−reserved | Confirmar semántica en F5; UI debe nombrar la elegida. |
| Fechas sin zona en Europe/Madrid | Otra zona de proveedor/ERP | Confirmar en F1; guardar día de pedido sin inventar hora. |
| EAN estricto con descarte de campo | Aceptar longitud sin checksum | Revisar pérdidas de EAN en F2, nunca relajar en silencio. |
| Make email + Sheets | Email + Airtable | Confirmar cuentas, destinatario y umbral en F10. |

Las alternativas no bloquean escribir el plan. Cambiar una regla durante implementación exige actualizar DATA_RULES, criterios, tests y ADR si corresponde.
