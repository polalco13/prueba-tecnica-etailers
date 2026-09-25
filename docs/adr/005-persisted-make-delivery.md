# 005 — Resumen persistido y entrega independiente a Make

## Estado

Implementación local F10: resumen, cliente y reenvío probados con MySQL temporal y HTTP simulado. Escenario real, conexiones, destinatario, envío autorizado, blueprint exportado y capturas pendientes. No se declara A09 cumplido.

## Contexto

La carga confirmada debe sobrevivir a un fallo de Make. Un reenvío días después no debe mezclar los contadores del run anterior con ventas o stock actuales. Un HTTP 2xx puede confirmar solo que Make ha encolado el webhook, y un timeout puede ocurrir después de ejecutar un destino.

## Decisión

- Guardar `etl-summary-v1` en `etl_runs.make_summary` en la misma transacción que completa las cuatro fuentes. Se calcula antes del commit y bajo el lock del escritor; el POST siempre ocurre después. Conserva fecha analítica, zona, contadores, umbral y cifras como texto Decimal, sin clientes ni credenciales.
- Solo los runs completados tienen resumen enviable en v1. Los fallos ETL conservan auditoría `failed` y salida 1; no se envían ventas viejas como si correspondieran al intento fallido. Alertar sobre fallos completos requeriría otro contrato explícito. La condición de calidad de una carga completada es `rows_rejected > threshold OR low_stock_count > 0`, con umbral inicial configurable 0. Duplicados y avisos no suman a rechazos.
- Sin URL configurada se guarda el resumen y no se envía. Con URL, un POST por invocación, sin redirecciones ni proxies del entorno, con timeout por operación de red (10 s por defecto). No se hace un reintento automático de una operación con posibles efectos externos: el CLI permite reenvío explícito con el mismo `run_id` y JSON.
- Estados de entrega: `not_applicable` (no configurada), `pending` (pendiente/intento iniciado), `accepted` (HTTP 2xx), `failed` (otro HTTP), `uncertain` (excepción de red). Intentos y fechas se confirman antes/después del HTTP. Una caída deja `pending` con intentos > 0; revisar Make antes de reenviar. Si falla la escritura de la respuesta HTTP, la carga ya publicada no se marca failed; el CLI informa salida 2.
- Un lock MySQL por run impide envíos locales concurrentes. Un resumen accepted no vuelve a enviarse salvo `--force`, que se reserva para recuperar destinos después de revisar Make. Nunca se reconstruyen resúmenes de runs antiguos sin JSON guardado.
- En Make, procesar webhooks secuencialmente y buscar el `run_id` en Sheets antes de añadir una fila. Email requiere una marca separada de entrega; la existencia de una fila de histórico no demuestra que se enviara el correo. Sigue existiendo una ventana de duplicación si Sheets o email completan el efecto pero se pierde la respuesta. No se promete exactamente una vez.

## Alternativas consideradas

- Revertir MySQL si falla Make: invalidaría datos ya confirmados y no puede deshacer un correo.
- Recalcular al reenviar: produciría un resumen diferente para el mismo run.
- Reintentar POST automáticamente ante cualquier fallo: puede duplicar efectos externos antes de que el operador revise el escenario.
- Construir un blueprint ficticio: no acredita módulos, conexiones ni ejecución real; se exportará desde Make cuando esté configurado.

## Consecuencias

La migración `004_make_delivery` añade metadatos sin modificar tablas de negocio. Es necesario aplicarla explícitamente; no actualiza volúmenes por sí sola. Un resumen con problemas de generación hace rollback de la publicación completa, conservando la anterior. Un fallo de HTTP posterior conserva la nueva publicación. La aceptación HTTP se audita separada de la verificación de destinos; F10 permanece parcial hasta completar la evidencia externa.
