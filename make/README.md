# Integración Make — F10

**Estado:** código local probado; pruebas sintéticas y primera ejecución del ETL real conectada con Sheets/Gmail acreditadas por el usuario el 27/09/2026. Blueprint real saneado con procesamiento secuencial, filtro inicial y entrada Raw confirmados. La fila real y su marca de correo están contrastadas; A09 acreditado. El reenvío del mismo run real también está observado: histórico/correo bloqueados. Los tres rechazos previstos del filtro inicial ya están observados. Quedan recuperación e importación; F10 sigue abierta. Distinguir HTTP simulado, datos sintéticos enviados a Make y carga real del ETL.

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

Después del filtro, tres módulos `JSON > Transform to JSON` convierten por separado `rows` [10], `rejected_by_reason[]` [13] y `low_stock_products[]` [14] del webhook. Cada campo Object contiene una sola ficha. Sus respectivas salidas JSON se mapean a las columnas G, H y L de `Add a Row [9]`; las demás columnas usan los campos simples del webhook y `email_sent_at` queda vacío. Add a Row usa entrada Raw, confirmada en la segunda exportación. La primera tenía `USER_ENTERED`; este cambio no modifica las filas ya existentes. El texto pegado de la hoja permite contrastar el importe visible, pero no acredita su tipo interno.

La [captura del primer histórico](capturas/f10-synthetic-history-first-run.png), aportada el 26/09/2026, muestra el envío atravesando el filtro y finalizando Add a Row. El texto de Sheets aportado después contiene una sola fila del run sintético `00000000-0000-4000-8000-000000000002`: los valores y los tres JSON coinciden con `alert.synthetic.json`, incluido `36.00`. Se detectó una cabecera duplicada en J1; el usuario confirmó su corrección a `revenue_previous_month`. La [captura del envío de alerta](capturas/f10-synthetic-alert-first-mail.png), aportada el 27/09/2026, muestra «Ejecución nueva» bloqueando la reinserción. No es todavía una prueba de repetición del correo ya marcado.

## Correo sintético recibido y configuración de envío

El usuario indicó Gmail y un destinatario propio de prueba en la conversación; no se versiona su dirección. Configuró la conexión y ejecutó manualmente el POST sintético. El 27/09/2026 aportó una captura del correo recibido: run terminado en `0002`, un producto, un rechazo, umbral 0, un producto bajo mínimos, motivo `NON_POSITIVE_PRICE`, detalle `SYNTHETIC-001` y facturación de 2026-08 `36.00`. Asunto usado: `[PRUEBA ETL Nortesur] Alerta de carga {{run_id}}`; cuerpo identificado expresamente como prueba sintética. La captura de Gmail no se incorpora porque incluye datos personales.

La segunda ruta del router usa `alert_required = true`, sin fallback, y corre después del histórico. `Search Rows [15]` busca el mismo run con límite 1. El filtro «Correo pendiente» exige `Row number > 0` **AND** `email_sent_at (O) Does not exist`. `Gmail [16]` mapea los campos simples del webhook y los JSON de motivos/bajo stock desde H/L de esta búsqueda. `Update a Cell [17]` va después de Gmail: Cell contiene la letra O seguida del **Row number** de Search Rows [15], y Value contiene:

```text
{{formatDate(now; "YYYY-MM-DD HH:mm:ss"; "UTC")}} UTC
```

Usar entrada Raw. El usuario confirmó la corrección de Cell tras haber mapeado inicialmente el contenido de `email_sent_at`; la captura de ejecución muestra Gmail [16] y Update a Cell [17] completados. La [captura de repetición del 27/09/2026](capturas/f10-synthetic-alert-repeat.png) muestra «Ejecución nueva» y «Correo pendiente» dejando pasar 0 bundles: Add a Row, Gmail y Update a Cell no se ejecutan de nuevo. Acredita el bloqueo del reenvío manual guiado. La [tabla aportada por el usuario](capturas/f10-synthetic-sheets-verified.md) confirma una fila por run y la marca `2026-09-27 14:10:01 UTC` solo en la alerta. La segunda exportación acredita `sequential=true`, entrada Raw en ambos módulos de escritura y las tres condiciones AND del filtro inicial. Esta repetición manual no prueba concurrencia.

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

El 27/09/2026, siguiendo la guía de envío manual de `summary.synthetic.json`, el usuario aportó la [captura sin alerta](capturas/f10-synthetic-no-alert.png). El run del ejemplo termina en `0001`, tiene duplicados, rechazos 0, umbral 0, bajo stock 0 y ambas listas vacías. El filtro del histórico deja pasar el bundle y los tres JSON/Add a Row completan la operación; «Hay alerta» deja pasar 0 bundles y el resto de esa ruta no se ejecuta. Esto verifica el bloqueo del correo en el límite `rows_rejected = threshold = 0` sin bajo stock. La [tabla de Sheets aportada después](capturas/f10-synthetic-sheets-verified.md) confirma las quince cabeceras, ambas filas y todos los valores/JSON de los ejemplos: run `0001` con FALSE, listas `[]` y O vacía; run `0002` con TRUE y fecha UTC en O. Se verificó la igualdad de contadores de cada fuente y el importe visible `36.00`; la transcripción no permite comprobar el tipo interno de la celda.

## Pruebas de rechazo del filtro inicial observadas

El 27/09/2026 el usuario aportó la [captura del filtro inicial bloqueando la ejecución](capturas/f10-invalid-schema-blocked.png), tras la prueba guiada que carga `summary.synthetic.json` y sustituye `schema_version` por `version-invalida`. El webhook completa su operación y «Resumen válido» deja pasar 0 bundles; el router y los módulos de Sheets/JSON/Gmail posteriores no se ejecutan. La captura no muestra el payload: la identificación del caso procede del comando guiado anterior. No acredita los casos de estado inválido/run_id ausente ni una carga real del ETL. Se conserva la imagen original sin edición; no contiene destinatarios ni URL del webhook visibles.

Después, el usuario aportó la [captura del estado inválido bloqueado](capturas/f10-invalid-status-blocked.png), tras la guía que carga el mismo ejemplo sin alerta y cambia únicamente `status` a `failed` en memoria antes del POST. Webhook [1] completa una operación; «Resumen válido» deja pasar 0 bundles y ningún módulo posterior se ejecuta. Se acredita el bloqueo observado en esta prueba sintética; la identificación de la entrada procede de la guía, porque la captura no muestra el payload ni se aportó un nuevo log de terminal. El comando guiado no modifica la fixture ni el estado de un run en MySQL. La imagen original se conserva sin edición y sin datos privados visibles. El agente no hizo un POST para esta revisión. Esta captura no comprueba run_id ausente; el caso posterior se documenta a continuación.

La [captura posterior sin run_id](capturas/f10-missing-run-id-blocked.png) corresponde a la guía que carga `summary.synthetic.json`, conserva `schema_version=etl-summary-v1` y `status=completed`, y elimina únicamente `run_id` en memoria antes del POST. Webhook [1] completa una operación y «Resumen válido» deja pasar 0 bundles; ningún módulo posterior se ejecuta. Se acredita el bloqueo observado en la prueba sintética, con identificación de la entrada por la guía: la captura no muestra el payload ni se aportó un resultado de terminal. Se conserva la imagen original sin edición y sin datos privados visibles. El agente no ejecutó el POST ni modificó fixtures/BD. Con esto quedan observados los tres casos previstos del filtro, por separado.

## Primera ejecución del ETL real conectada con Make

El 27/09/2026 el usuario ejecutó el ETL y aportó logs y capturas para el run `c1a93f67-6990-4748-8efa-c18bc6777b42`. Se publicó el negocio antes del POST, y la [captura del escenario](capturas/f10-real-etl-destinations.png) muestra histórico/alerta y escritura de la marca completados. La captura del correo recibido contiene el mismo UUID, 115 productos, 72 rechazados, umbral 0, 12 productos bajo mínimos y facturación de agosto `56696.84`; no se versiona por contener datos personales. [Transcripción y alcance](capturas/f10-real-etl-evidence.md): contadores por fuente conciliados, diez motivos que suman 73 filas/motivos y doce entradas de bajo stock conocidas. No confundir estos datos con los ejemplos sintéticos. La [fila completa de Sheets](capturas/f10-real-sheets-verified.md) confirma una sola fila, status completed, `as_of=2026-09-27`, todos los contadores/JSON y O con `2026-09-27 15:34:53 UTC` (17:34:53 Europe/Madrid). A09 queda acreditado; no se ha consultado la BD del usuario ni ejecutado un POST adicional para esta revisión.

## Reenvío del resumen real verificado

El usuario ejecutó `--resend-make c1a93f67-6990-4748-8efa-c18bc6777b42 --force` y aportó el log de aceptación HTTP a las `17:53:55,949` y la [captura posterior](capturas/f10-real-etl-repeat.png). «Resumen válido» y «Hay alerta» dejan pasar 1 bundle; «Ejecución nueva» y «Correo pendiente» dejan pasar 0. Search Rows [3]/agregador [7]/Search Rows [15] completan una operación; JSON/Add a Row/Gmail/Update a Cell no se ejecutan. Acredita que ese reenvío del escenario no reinserta la fila, no manda otro correo ni vuelve a escribir la marca. No se aportó una nueva lectura de las celdas de Sheets, un código de salida numérico ni una prueba concurrente. [Detalle y alcance](capturas/f10-real-etl-evidence.md#reenvío-manual-del-mismo-run-27092026).

## Validación pendiente de la cuenta

- Simular un fallo del destino y documentar recuperación/riesgo residual. Los casos de versión incorrecta, estado inválido y run_id ausente ya se observaron bloqueados sin ejecutar destinos.
- Comprobar la importación de la copia saneada en un escenario desactivado con conexiones propias. La validación local del JSON no acredita una importación en Make.

## Blueprint exportado y revisión del 27/09/2026

[escenario.blueprint.json](escenario.blueprint.json) procede de la segunda exportación real `make-etl.json` aportada por el usuario; sustituye la copia saneada de `nortesur-make.json`. Ambos originales se conservan sin modificar fuera del repositorio. Se retiraron el identificador del webhook, identificadores/etiquetas personales de conexiones, identificadores/selecciones de la hoja y destinatario. No se fabricaron conexiones alternativas. Se conservan módulos, IDs, versiones, rutas, filtros, fórmulas, estructura del webhook y ajustes funcionales del export. Frente a la primera copia, los únicos cambios funcionales son el filtro inicial y la entrada Raw en Add a Row.

La revisión confirma `metadata.scenario.sequential=true`, histórico primero, búsquedas exactas por run con límite 1, filtro del bundle vacío, serialización de G/H/L y marca `O{{15.__ROW_NUMBER__}}` posterior al correo con entrada Raw. El cuerpo exportado empieza por «Resumen de la ejecución del ETL.»; el asunto mantiene `[PRUEBA ETL Nortesur]`. Las capturas anteriores acreditan pruebas sintéticas. La evidencia posterior del [ETL real](capturas/f10-real-etl-evidence.md) confirma recepción de este cuerpo con el nuevo UUID y cifras reales de la carga.

Dos correcciones **confirmadas en la segunda exportación**:

1. Google Sheets **Add a Row [9]** contiene **Value input option = Raw**, valor `RAW` en el JSON. [Make documenta](https://apps.make.com/google-sheets-modules) que User entered interpreta números/fechas y Raw conserva los valores recibidos. Update a Cell [17] ya usa Raw. El importe visible `36.00` de las pruebas previas no demuestra que la celda se guardara como texto.
2. La conexión **Webhook [1] → Router [2]** contiene el filtro **Resumen válido** con tres condiciones AND: `1.schema_version` **Text operators: Equal to** `etl-summary-v1`; `1.status` **Text operators: Equal to** `completed`; `1.run_id` **Basic operators: Exists**. Elegir las fichas del webhook; no escribir los nombres como texto literal. [Exists comprueba que el campo esté informado](https://help.make.com/filtering). Su presencia/configuración se comprueba en el export; las pruebas guiadas de versión incorrecta, estado inválido y run_id ausente ya se observaron bloqueadas, por separado, antes del router.

### Conexiones al importar

Importar el archivo desde el menú **Import blueprint** de un escenario nuevo y desactivado. [Make requiere configurar las conexiones propias tras importar](https://help.make.com/blueprints); esta copia no contiene accesos reutilizables.

1. Crear/seleccionar un Custom webhook en [1]. Usar su URL únicamente en la configuración local privada; la estructura de campos queda en el blueprint.
2. Autorizar Google Sheets y seleccionar la misma hoja/tab `ejecuciones` en [3], [9], [15] y [17]. Preparar las quince cabeceras en el orden documentado, A–O; verificar búsquedas A, mapeos A–N y actualización O. Las conexiones y `spreadsheetId` están sin asignar.
3. Autorizar Gmail [16], introducir un destinatario de prueba propio y revisar asunto/cuerpo. La lista de destinatarios se deja vacía deliberadamente.
4. Comprobar que se conservan el filtro inicial, ambas entradas Raw y **Process data in order**; guardar y probar de forma controlada antes de activarlo. La importación aún no se ha ejecutado; no se declara este archivo probado dentro de Make.

A09 queda acreditado con ejecución real, ambos destinos y fila final contrastada. F10 sigue pendiente de las verificaciones indicadas. F11 no se ha iniciado.

## Referencias y decisión técnica

- [Webhooks y confirmación HTTP de Make](https://help.make.com/webhooks).
- [Procesamiento secuencial](https://help.make.com/scenario-settings).
- [Exportar/importar blueprints y recrear conexiones](https://help.make.com/blueprints).
- [Google Sheets: entrada Raw y User entered](https://apps.make.com/google-sheets-modules).
- [Filtros y operador Exists](https://help.make.com/filtering).
- [ADR 005](../docs/adr/005-persisted-make-delivery.md): persistencia, reenvío y límites de entrega.
