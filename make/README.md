# Integración Make — F10

**Estado:** código local implementado y probado; el usuario verificó el contenido del histórico y el 27/09/2026 aportó evidencia del correo sintético recibido, Gmail/Update a Cell completados y reenvío bloqueado por ambos filtros. Pendientes revisión del valor de `email_sent_at`, casos sin alerta, recuperación, envío del ETL real y blueprint: F10/A09 sigue abierta. Distinguir HTTP simulado, datos sintéticos enviados a Make y carga real del ETL.

## Configuración y comandos

Aplicar `.venv/bin/python -m src.db migrate` para añadir `004_make_delivery`. Conserva las tablas de negocio y permite retomar la migración tras una interrupción.

Variables opcionales en `.env` local (no versionarlo):

| Variable | Valor inicial | Significado |
| --- | --- | --- |
| `MAKE_WEBHOOK_URL` | vacío | URL HTTPS secreta del webhook; vacío = no enviar |
| `MAKE_TIMEOUT` | 10 | Timeout en segundos por operación de red, rango 1–60 |
| `MAKE_REJECTION_THRESHOLD` | 0 | Umbral absoluto entero, rango 0–1.000.000; alerta si rechazos **superan** el umbral o hay bajo stock |

No configurar la URL de un escenario con email hasta revisar los destinos y autorizar la prueba. No pegar la URL en terminal, documentación, capturas ni Git. La URL no se guarda en MySQL.

```bash
# Ejecuta ETL; si MAKE_WEBHOOK_URL está configurada, envía tras el commit.
.venv/bin/python -m src.etl

# Reenvía únicamente el resumen guardado, sin leer fuentes ni volver a cargar negocio.
.venv/bin/python -m src.etl --resend-make RUN_ID

# Solo después de revisar Make: permite repetir un POST ya aceptado por HTTP.
.venv/bin/python -m src.etl --resend-make RUN_ID --force
```

Salidas: **0** = ETL publicado y entrega desactivada/aceptada por HTTP, o reenvío aceptado; **1** = ETL/configuración fallida; **2** = negocio publicado pero entrega no confirmada, o fallo del reenvío. `accepted` no acredita ni la fila de Sheets ni el correo. Un 500, 429 o timeout no se reintenta automáticamente; revisar la ejecución en Make y reenviar el mismo run cuando proceda.

Para ver el estado en DBeaver:

```sql
SELECT id, status, make_status, make_attempts, make_error_code,
       make_last_attempt_at, make_accepted_at, make_summary
FROM etl_runs ORDER BY started_at DESC LIMIT 10;
```

`pending` con intentos > 0 tras una caída puede significar que Make sí recibió el POST. `uncertain` indica error de red con efecto remoto desconocido. Un run anterior a F10 sin resumen no se puede reenviar: no se reconstruye con cifras actuales.

## Contrato efectivo `etl-summary-v1`

Los ejemplos [normal](examples/summary.synthetic.json) y [con alerta](examples/alert.synthetic.json) son sintéticos, no evidencia real ni blueprints. Usar el de alerta para definir la estructura de colecciones porque sus listas tienen elementos; probar también el normal con listas vacías. Este contrato sustituye los ejemplos preliminares de conversación.

| Campo | Contenido |
| --- | --- |
| `schema_version`, `run_id`, `status` | Versión, UUID estable, `completed` |
| `finished_at`, `as_of`, `business_timezone`, `rules_version` | Fecha UTC de publicación, día analítico congelado, zona y reglas ETL |
| `products_loaded` | Productos válidos del catálogo en el lote, sin contar históricos ni affected_rows |
| `rows` | Contadores de `catalog_csv`, `stock_api` y `orders_csv`: `rows_read`, `rows_accepted`, `rows_rejected`, `rows_deduplicated`, `quality_warnings`, `discarded_fields`, más los contadores específicos existentes de cada fuente |
| `rows_rejected` | Suma de filas rechazadas de las tres fuentes, sin duplicados/avisos |
| `rejected_by_reason` | Lista de `{source, reason_code, rows}`; cada localizador cuenta una vez por motivo; varios motivos pueden superar el total de filas rechazadas |
| `revenue_previous_month`, `previous_month` | Importe **string decimal**, obtenido del SQL F8, y mes natural anterior completo (`YYYY-MM`) |
| `currency`, `tax_basis` | `null` y `unconfirmed`: no confirmar EUR/IVA sin evidencia |
| `low_stock_count`, `low_stock_products` | Conteo/lista F8 de SKU comercial, nombre, stock físico conocido <5 y unidades vendidas en los tres meses naturales anteriores |
| `rejection_threshold`, `alert_required` | Umbral congelado y condición calculada con `rows_rejected > threshold OR low_stock_count > 0` |

Por fuente: `read = accepted + rejected + deduplicated`. `quality_warnings` y `discarded_fields` no se suman a esta igualdad. No enviar campos `raw_excerpt`, clientes ni líneas completas. Los fallos completos del ETL quedan en auditoría local y no generan resumen v1 ni un mensaje de éxito con ceros.

## Configuración del escenario

1. Iniciar sesión en Make y crear un escenario `Nortesur — resumen ETL`. Crear `Webhooks > Custom webhook`. Definir la estructura con el ejemplo sintético; no conectar un envío real mientras los destinos no estén revisados.
2. Validar `schema_version = etl-summary-v1`, `status = completed` y `run_id` no vacío. Activar procesamiento secuencial (**Process data in order**) para que dos reenvíos no hagan simultáneamente buscar/añadir la misma fila.
3. Añadir un router con ruta de **histórico siempre** y ruta de **email condicional** (`alert_required = true`). No son rutas excluyentes: una ejecución problemática también debe quedar en el histórico. Ordenar histórico primero.
4. Histórico: buscar `run_id` por coincidencia exacta en Google Sheets; si ya existe, no insertar. Si no existe, añadir una fila. Configurar la búsqueda para continuar cuando no encuentre resultados y comprobar este caso. Guardar por separado `email_sent_at`, inicialmente vacío. No sobrescribir esa marca al reenviar.
5. Email: si hay alerta, consultar la fila del mismo run y enviar solo si `email_sent_at` está vacío. Tras éxito, actualizar esa marca. La fila puede existir aunque el correo haya fallado; no usar simplemente «existe run_id» para descartar la alerta. Si el envío funciona pero falla la actualización de la marca, puede duplicarse al reintentar; revisar el historial antes de hacerlo. No añadir otro Data Store si la hoja basta.
6. Los errores de Sheets/email deben permanecer visibles en Make. No ignorarlos ni fabricar un resultado correcto. Un 2xx del webhook puede ser solo encolado; verificar los dos destinos en el historial del escenario.

Columnas recomendadas para la hoja: `run_id`, `finished_at`, `status`, `as_of`, `products_loaded`, `rows_rejected`, `rows_json`, `rejected_by_reason_json`, `previous_month`, `revenue_previous_month`, `low_stock_count`, `low_stock_products_json`, `rejection_threshold`, `alert_required`, `email_sent_at`. Guardar el importe como texto para conservar sus dos decimales; no recalcular dinero en Make. Los objetos/listas pueden serializarse como JSON para no perder métricas de fuente.

### Ruta de histórico montada en la cuenta de prueba

`Search Rows [3]` busca exactamente el `run_id` del webhook, con límite 1. `Array aggregator [7]` usa Search Rows como fuente, agrega `run_id (A)` y `Row number`, deja Group by vacío y no detiene una agregación vacía. Se observó que una búsqueda sin filas emite un bundle con campos vacíos: el agregador produce una lista de longitud 1. Por tanto, **no usar `length(array) = 0` como criterio de inserción** en esta configuración.

El filtro «Ejecución nueva» obtiene el número de fila del primer resultado, con valor 0 si está vacío:

```text
{{ifempty(get(7.array; "1.__ROW_NUMBER__"); 0)}}
Numeric operators: Equal to
0
```

El 7 es el ID del agregador observado; adaptar esa referencia si cambia al montar otro escenario. Pegar la expresión con sus dobles llaves o construirla con funciones/fichas: texto literal como `length(7.Array[])` no es una fórmula.

Después del filtro, tres módulos `JSON > Transform to JSON` convierten por separado `rows` [10], `rejected_by_reason[]` [13] y `low_stock_products[]` [14] del webhook. Cada campo Object contiene una sola ficha. Sus respectivas salidas JSON se mapean a las columnas G, H y L de `Add a Row [9]`; las demás columnas usan los campos simples del webhook y `email_sent_at` queda vacío. Sheets usa entrada Raw.

La [captura del primer histórico](capturas/f10-synthetic-history-first-run.png), aportada el 26/09/2026, muestra el envío atravesando el filtro y finalizando Add a Row. El texto de Sheets aportado después contiene una sola fila del run sintético `00000000-0000-4000-8000-000000000002`: los valores y los tres JSON coinciden con `alert.synthetic.json`, incluido `36.00`. Se detectó una cabecera duplicada en J1; el usuario confirmó su corrección a `revenue_previous_month`. La [captura del envío de alerta](capturas/f10-synthetic-alert-first-mail.png), aportada el 27/09/2026, muestra «Ejecución nueva» bloqueando la reinserción. No es todavía una prueba de repetición del correo ya marcado.

## Correo sintético recibido y configuración de envío

El usuario indicó Gmail y un destinatario propio de prueba en la conversación; no se versiona su dirección. Configuró la conexión y ejecutó manualmente el POST sintético. El 27/09/2026 aportó una captura del correo recibido: run terminado en `0002`, un producto, un rechazo, umbral 0, un producto bajo mínimos, motivo `NON_POSITIVE_PRICE`, detalle `SYNTHETIC-001` y facturación de 2026-08 `36.00`. Asunto usado: `[PRUEBA ETL Nortesur] Alerta de carga {{run_id}}`; cuerpo identificado expresamente como prueba sintética. La captura de Gmail no se incorpora porque incluye datos personales.

La segunda ruta del router usa `alert_required = true`, sin fallback, y corre después del histórico. `Search Rows [15]` busca el mismo run con límite 1. El filtro «Correo pendiente» exige `Row number > 0` **AND** `email_sent_at (O) Does not exist`. `Gmail [16]` mapea los campos simples del webhook y los JSON de motivos/bajo stock desde H/L de esta búsqueda. `Update a Cell [17]` va después de Gmail: Cell contiene la letra O seguida del **Row number** de Search Rows [15], y Value contiene:

```text
{{formatDate(now; "YYYY-MM-DD HH:mm:ss"; "UTC")}} UTC
```

Usar entrada Raw. El usuario confirmó la corrección de Cell tras haber mapeado inicialmente el contenido de `email_sent_at`; la captura de ejecución muestra Gmail [16] y Update a Cell [17] completados. La [captura de repetición del 27/09/2026](capturas/f10-synthetic-alert-repeat.png) muestra «Ejecución nueva» y «Correo pendiente» dejando pasar 0 bundles: Add a Row, Gmail y Update a Cell no se ejecutan de nuevo. Acredita el bloqueo del reenvío manual guiado; falta comprobar directamente el valor escrito en O. El procesamiento secuencial y el filtro inicial de contrato se han indicado, pero su configuración no se ha acreditado con captura/exportación; esta repetición manual no prueba concurrencia.

Para una futura prueba de ETL real, sustituir el asunto y la identificación sintética del cuerpo por contenido acorde con la fuente utilizada, y revisar el destino. Plantilla prevista para datos del ETL:

```text
[ETL Nortesur] Revisión de la carga {{run_id}}
```

Cuerpo propuesto (texto plano; mapear los campos en el módulo de correo):

```text
La carga {{run_id}} terminó y sus datos se publicaron el {{finished_at}}.

Productos de catálogo cargados: {{products_loaded}}
Filas rechazadas: {{rows_rejected}} (umbral: {{rejection_threshold}})
Motivos por fuente: {{rejected_by_reason}}
Productos bajo mínimos: {{low_stock_count}}
Detalle de bajo stock: {{low_stock_products}}
Facturación operativa de {{previous_month}}: {{revenue_previous_month}}
Moneda y base fiscal pendientes de confirmar.

Revisar el dashboard y las incidencias de este run.
```

La autorización debe concretar destinatario y prueba antes de disparar un webhook capaz de enviar este email; lo exige AGENTS. No hace falta incluir ni mandar el correo de entrega final del README durante F10.

## Prueba sin alerta ejecutada

El 27/09/2026, siguiendo la guía de envío manual de `summary.synthetic.json`, el usuario aportó la [captura sin alerta](capturas/f10-synthetic-no-alert.png). El run del ejemplo termina en `0001`, tiene duplicados, rechazos 0, umbral 0, bajo stock 0 y ambas listas vacías. El filtro del histórico deja pasar el bundle y los tres JSON/Add a Row completan la operación; «Hay alerta» deja pasar 0 bundles y el resto de esa ruta no se ejecuta. Esto verifica el bloqueo del correo en el límite `rows_rejected = threshold = 0` sin bajo stock. Falta revisar directamente la nueva fila, los JSON vacíos y las marcas de envío de ambas filas en Sheets.

## Validación pendiente de la cuenta

- Revisar la fila del ejemplo sin alerta en Sheets: run terminado en `0001`, duplicados >0, rechazos 0, bajo stock 0, listas `[]` y O vacía. Make ya acredita Add a Row completado y ruta de correo bloqueada.
- Revisar directamente el valor de `email_sent_at` en O. La repetición manual del run sintético ya dejó histórico y Gmail bloqueados, después del primer correo recibido.
- Acreditar el procesamiento secuencial y el filtro inicial de contrato. Simular un fallo del destino y documentar recuperación/riesgo residual.
- Una carga real de las cuatro fuentes → verificar recepción **y** destinos; no basta con el log HTTP del ETL. Configurar destino de prueba antes de ejecutarla.
- Exportar desde Make `escenario.blueprint.json`, revisar/sanitizar URLs de webhook, conexiones, identificadores privados, destinatarios y muestras de clientes. Guardar capturas del escenario y de una ejecución en `capturas/`, sin secretos. Documentar qué conexiones hay que recrear al importar.

No existe todavía `escenario.blueprint.json` porque no se ha exportado. El usuario ya inició sesión, conectó Sheets/Gmail y verificó histórico y recepción de correo con datos sintéticos; falta completar las verificaciones de arriba para cerrar F10/A09. F11 no se ha iniciado.

## Referencias y decisión técnica

- [Webhooks y confirmación HTTP de Make](https://help.make.com/webhooks).
- [Procesamiento secuencial](https://help.make.com/scenario-settings).
- [Exportar/importar blueprints y recrear conexiones](https://help.make.com/blueprints).
- [ADR 005](../docs/adr/005-persisted-make-delivery.md): persistencia, reenvío y límites de entrega.
