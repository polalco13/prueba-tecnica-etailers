# ETL real → Make — evidencia aportada por el usuario

El 27/09/2026 el usuario ejecutó `.venv/bin/python -m src.etl` desde el proyecto y aportó los logs de terminal, la [captura del escenario](f10-real-etl-destinations.png) y una captura del correo recibido. Esta última no se versiona porque contiene nombre, dirección y fotografía personales. Los datos siguientes son una transcripción de esas evidencias; no son una fixture ni una nueva ejecución realizada por el agente.

Run: `c1a93f67-6990-4748-8efa-c18bc6777b42`.

## Logs aportados

La migración informó a las 17:34:14 que `004_make_delivery` ya estaba aplicada. Los siguientes eventos incluyen el mismo run_id; las horas se conservan como aparecieron en terminal, sin atribuirles un offset que el log no muestra:

| Hora del log | Evento |
| --- | --- |
| 17:34:47,936 | Stock descargado: 5 páginas y 230 filas |
| 17:34:47,953 | Extracción validada: 115 productos |
| 17:34:50,394 | Catálogo, tarifas, stock y pedidos publicados |
| 17:34:50,588 | Resumen recibido por HTTP; destinos pendientes de verificar en Make |
| 17:34:50,590 | Contadores finales por fuente |

| Fuente | Leídas | Aceptadas | Rechazadas | Deduplicadas |
| --- | --- | --- | --- | --- |
| Catálogo CSV | 133 | 115 | 15 | 3 |
| Stock API | 230 | 206 | 24 | 0 |
| Pedidos CSV | 1142 | 1101 | 33 | 8 |

Se cargaron 358 pedidos, 30 parciales. Por fuente se cumple `leídas = aceptadas + rechazadas + deduplicadas`; hay 72 filas rechazadas en total y 11 deduplicadas, contadas aparte.

## Destinos y correo

La captura del escenario muestra «Resumen válido», «Ejecución nueva», «Hay alerta» y «Correo pendiente» dejando pasar un bundle. Search Rows [3]/agregador [7]/JSON [10,13,14]/Add a Row [9] completan el histórico; Search Rows [15]/Gmail [16]/Update a Cell [17] completan la alerta y la escritura de su marca.

El correo recibido tiene el mismo UUID en asunto y cuerpo, empieza por «Resumen de la ejecución del ETL.» y muestra:

| Campo | Valor visible |
| --- | --- |
| Productos cargados | 115 |
| Filas rechazadas | 72 |
| Umbral de rechazos | 0 |
| Productos bajo mínimos | 12 |
| Mes anterior | 2026-08 |
| Facturación del mes anterior | 56696.84 |
| Moneda/base fiscal | Pendientes de confirmar |

La alerta corresponde a la regla documentada: `72 > 0` y también hay bajo stock. Asunto conservado: `[PRUEBA ETL Nortesur] Alerta de carga …`; los datos proceden de esta ejecución del ETL, no de los ejemplos sintéticos.

La distribución visible en el correo es:

| Fuente | Motivo | Filas por motivo |
| --- | --- | --- |
| catalog_csv | AMBIGUOUS_NUMBER | 5 |
| catalog_csv | CONFLICTING_PRODUCT_SKU | 3 |
| catalog_csv | INVALID_COLUMN_COUNT | 2 |
| catalog_csv | MISSING_REQUIRED_FIELD | 1 |
| catalog_csv | NON_POSITIVE_PRICE | 4 |
| orders_csv | INVALID_QUANTITY | 9 |
| orders_csv | INVALID_QUANTITY_FOR_STATUS | 8 |
| orders_csv | MISSING_ORDER_DATE | 1 |
| orders_csv | MISSING_REQUIRED_FIELD | 16 |
| stock_api | UNKNOWN_PRODUCT_SKU | 24 |

Suma 73 filas/motivos frente a 72 filas rechazadas: una fila puede tener varios motivos distintos. El detalle de bajo stock contiene doce entradas visibles, todas con stock físico inferior a 5 y unidades recientes positivas:

| SKU | Stock físico | Unidades recientes |
| --- | --- | --- |
| PRV-2056 | 0 | 12 |
| PRV-2081 | 0 | 4 |
| PRV-2111 | 1 | 50 |
| PRV-2110 | 1 | 25 |
| PRV-2061 | 1 | 5 |
| PRV-2118 | 1 | 5 |
| PRV-2028 | 1 | 3 |
| PRV-2075 | 1 | 3 |
| PRV-2083 | 3 | 7 |
| PRV-2068 | 3 | 5 |
| PRV-2112 | 3 | 2 |
| PRV-2074 | 3 | 1 |

## Reenvío manual del mismo run (27/09/2026)

El usuario ejecutó el comando siguiente después de contrastar los destinos y la marca de correo:

```bash
.venv/bin/python -m src.etl --resend-make c1a93f67-6990-4748-8efa-c18bc6777b42 --force
```

El log aportado registra a las `17:53:55,949` «Resumen recibido por HTTP; destinos pendientes de verificar en Make» para ese mismo UUID. No se observa una nueva carga de fuentes: el comando reutiliza el resumen persistido. No se aportó un código numérico de salida ni una consulta SQL de sus metadatos de entrega.

La [captura posterior](f10-real-etl-repeat.png) muestra:

| Filtro | Bundles que pasan |
| --- | --- |
| Resumen válido | 1 |
| Ejecución nueva | 0 |
| Hay alerta | 1 |
| Correo pendiente | 0 |

Search Rows [3], Array aggregator [7] y Search Rows [15] completan una operación. Los tres módulos JSON [10,13,14], Add a Row [9], Gmail [16] y Update a Cell [17] no se ejecutan. Acredita el bloqueo de reinserción y de otro envío de correo en esta ejecución del escenario, además de que la marca no se vuelve a escribir. La captura no contiene las celdas de Sheets posteriores a la prueba: no es una nueva lectura de O ni una comprobación de todas las escrituras posibles fuera de este escenario. Tampoco es una prueba de concurrencia.

Se conserva la imagen original sin edición, sin URL del webhook ni datos de conexiones/destinatarios visibles. El agente registró la evidencia y revisó documentación; no ejecutó este reenvío ni otro POST.

## Alcance de la verificación

Los logs prueban la publicación anterior al POST y la captura acredita la ejecución correcta de ambos destinos; la recepción del correo deja de depender de la aceptación HTTP como única evidencia. Sus cifras coinciden con los contadores aportados y con los importes/conteos de la validación SQL previa F8, sin asumir que las entradas o la fecha analítica sean idénticas.

El texto de Sheets aportado después confirma las quince celdas de [una sola fila del run real](f10-real-sheets-verified.md), `status=completed`, `as_of=2026-09-27` y `finished_at=2026-09-27T15:34:50.365441Z`. Los contadores y los tres JSON coinciden con las evidencias anteriores. O contiene `2026-09-27 15:34:53 UTC` (17:34:53 Europe/Madrid), posterior a finished_at y coherente con la recepción visible a las 17:34. La marca no mide de forma independiente la hora de entrega del servidor de correo.

El run_id enlaza publicación, ambos destinos, correo recibido, fila final y reenvío bloqueado: A09 queda acreditado. No se ha consultado la BD del usuario ni ejecutado un POST adicional en esta revisión. El texto no acredita el tipo interno de las celdas; tampoco se ha verificado la importación del blueprint ni recuperación tras un fallo de destino. Los casos sintéticos anteriores de bloqueo de reenvío y ausencia de alerta se conservan por separado. F10 sigue abierta por las verificaciones restantes; F11 no iniciado.
