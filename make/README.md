# Integración Make — F10

**Estado:** código local implementado y probado; escenario real y A09 pendientes. No hay todavía un blueprint exportado ni capturas de destinos. No confundir pruebas HTTP simuladas con una ejecución de Make.

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

## Montaje real pendiente

1. Iniciar sesión en Make y crear un escenario `Nortesur — resumen ETL`. Crear `Webhooks > Custom webhook`. Definir la estructura con el ejemplo sintético; no conectar un envío real mientras los destinos no estén revisados.
2. Validar `schema_version = etl-summary-v1`, `status = completed` y `run_id` no vacío. Activar procesamiento secuencial (**Process data in order**) para que dos reenvíos no hagan simultáneamente buscar/añadir la misma fila.
3. Añadir un router con ruta de **histórico siempre** y ruta de **email condicional** (`alert_required = true`). No son rutas excluyentes: una ejecución problemática también debe quedar en el histórico. Ordenar histórico primero.
4. Histórico: buscar `run_id` por coincidencia exacta en Google Sheets; si ya existe, no insertar. Si no existe, añadir una fila. Configurar la búsqueda para continuar cuando no encuentre resultados y comprobar este caso. Guardar por separado `email_sent_at`, inicialmente vacío. No sobrescribir esa marca al reenviar.
5. Email: si hay alerta, consultar la fila del mismo run y enviar solo si `email_sent_at` está vacío. Tras éxito, actualizar esa marca. La fila puede existir aunque el correo haya fallado; no usar simplemente «existe run_id» para descartar la alerta. Si el envío funciona pero falla la actualización de la marca, puede duplicarse al reintentar; revisar el historial antes de hacerlo. No añadir otro Data Store si la hoja basta.
6. Los errores de Sheets/email deben permanecer visibles en Make. No ignorarlos ni fabricar un resultado correcto. Un 2xx del webhook puede ser solo encolado; verificar los dos destinos en el historial del escenario.

Columnas recomendadas para la hoja: `run_id`, `finished_at`, `status`, `as_of`, `products_loaded`, `rows_rejected`, `rows_json`, `rejected_by_reason_json`, `previous_month`, `revenue_previous_month`, `low_stock_count`, `low_stock_products_json`, `rejection_threshold`, `alert_required`, `email_sent_at`. Guardar el importe como texto para conservar sus dos decimales; no recalcular dinero en Make. Los objetos/listas pueden serializarse como JSON para no perder métricas de fuente.

## Correo preparado, aún no enviado

Destinatario y conexión de salida: **pendientes de confirmar**. Asunto propuesto:

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

## Validación pendiente de la cuenta

- Prueba sintética identificada: duplicados >0, rechazos 0, sin bajo stock → una fila de histórico y ningún email.
- Prueba de alerta autorizada: rechazos por encima del umbral o bajo stock → histórico y email. En el límite exacto del umbral, sin bajo stock, no hay alerta.
- Repetición del mismo run → una sola fila; correo ya marcado no se repite. Simular un fallo del destino y documentar recuperación/riesgo residual.
- Una carga real de las cuatro fuentes → verificar recepción **y** destinos; no basta con el log HTTP del ETL. Configurar destino de prueba antes de ejecutarla.
- Exportar desde Make `escenario.blueprint.json`, revisar/sanitizar URLs de webhook, conexiones, identificadores privados, destinatarios y muestras de clientes. Guardar capturas del escenario y de una ejecución en `capturas/`, sin secretos. Documentar qué conexiones hay que recrear al importar.

No existe todavía `escenario.blueprint.json` porque no se ha exportado un escenario real. El acceso revisado en esta tarea mostró la pantalla de login; falta completar estas verificaciones para cerrar F10/A09. F11 no se ha iniciado.

## Referencias y decisión técnica

- [Webhooks y confirmación HTTP de Make](https://help.make.com/webhooks).
- [Procesamiento secuencial](https://help.make.com/scenario-settings).
- [Exportar/importar blueprints y recrear conexiones](https://help.make.com/blueprints).
- [ADR 005](../docs/adr/005-persisted-make-delivery.md): persistencia, reenvío y límites de entrega.
