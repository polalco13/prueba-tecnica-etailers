# 002 — Carga idempotente por instantáneas completas

## Estado

Propuesto. Validar en F6 que el CSV de pedidos representa una exportación completa, no un delta.

## Contexto

El README exige repetir el ETL sin duplicar productos ni pedidos. Hay duplicados en origen y las líneas no tienen ID estable. Un simple INSERT duplica datos; un upsert de hash sin reconciliación acumularía versiones antiguas cuando una línea cambie. La API puede fallar después de algunas páginas.

## Decisión

Usar claves únicas naturales para SKU y pedido, y firma canónica versionada SHA-256 de pedido/SKU/cantidad/precio/descuento para líneas. Deduplicar firmas iguales con trazabilidad, declarando que no se distinguen dos líneas legítimas idénticas. Publicar instantáneas completas: upserts de entidades, eliminación explícita de líneas/pedidos que ya no pertenezcan al conjunto aceptado y actualización de stock por almacén. Productos ausentes pasan a históricos, no se borran.

Extraer y validar antes de una transacción MySQL de negocio; snapshot ilegible, extracción incompleta o fichero inesperadamente vacío abortan. Publicar las cuatro fuentes de manera atómica. Solo una ejecución concurrente. Rechazos y runs fallidos quedan auditados separadamente; runs completados se confirman con el negocio. Enviar Make después del commit, con run_id reutilizable para reintento de entrega.

Con entradas/reglas idénticas, el contenido de negocio permanece idéntico. Auditoría/timestamps/notificaciones por ejecución pueden aumentar. Comparar mediante valores y claves de negocio, excluyendo metadatos del run.

## Alternativas consideradas

- INSERT ciego: incumple idempotencia.
- Hash por línea sin borrar firmas antiguas: no gestiona correcciones.
- Número físico de fila como identidad: cambia al reordenar o insertar filas en el CSV.
- Conservar multiplicidad con índice de ocurrencia: preserva líneas legítimas iguales, pero también duplicados accidentales; alternativa si el proveedor confirma esa semántica.
- ID de línea del ERP: preferible cuando exista, no está en la fuente actual.
- TRUNCATE y recarga: dificulta FKs y publicación atómica; no usar ni borrar volumen para reiniciar.
- Incremental desde el principio: exige watermark, bajas y reglas de reconciliación no necesarias para el primer objetivo; reservar a F11.

## Consecuencias

Se necesita reconciliar el conjunto aceptado, no solo escribir registros. Una fila que deja de ser válida no debe conservar silenciosamente el valor anterior en la versión actual. Tests cubren repetición, corrección, desaparición, fallo y concurrencia. La política de deduplicación y autoridad del snapshot es un supuesto de negocio relevante que debe confirmarse y permanecer visible. Para cinco millones de líneas se preferirán staging y procesamiento por lotes sin cambiar el contrato externo de publicación.
