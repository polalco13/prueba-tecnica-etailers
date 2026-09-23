# Reglas propuestas de calidad de datos

Estado: decisiones D y supuestos S para implementar y verificar, no resultados de limpieza. Requisitos R: [README.md](README.md). Arquitectura y métricas: [TECH_SPEC.md](TECH_SPEC.md). Las reglas serán versionadas junto al código; ningún cambio silencioso en semántica.

## Evidencia y convenciones

Inspección limitada: cabeceras, primeras filas, unos ejemplos de anomalías, XML y primeras observaciones de stock. Solo se recorrieron globalmente estado/canal para conocer sus etiquetas distintas; no se calcularon resultados económicos ni conteos de carga/rechazo.

Catálogo tiene 11 columnas: `sku, ean, nombre, marca, categoria, precio_coste, pvp_recomendado, iva, peso_kg, fecha_alta, descripcion`. Pedidos tiene 9: `id_pedido, fecha_pedido, cliente, canal, estado, sku, cantidad, precio_unitario, descuento_linea`. La muestra incluye columnas de más y de menos, fechas heterogéneas, EAN científico y pedidos con campos vacíos. Stock usa `sku, warehouse, quantity, reserved, updated_at`. XML tiene reglas de categoría/marca, volumen y precios pactados por SKU.

Acciones: **normalizar** conserva el valor semántico; **rechazar fila** excluye entidad/línea; **descartar campo** conserva entidad con campo NULL y trazabilidad; **deduplicar** excluye ocurrencia redundante; **avisar** conserva registro con advertencia; **abortar** impide publicar todo el lote. La tabla rejections registra también campos descartados y avisos con acción/severidad, diferenciados del rechazo de filas.

## Matriz de reglas

| Problema | Fuente | Regla propuesta | Acción | Motivo / observabilidad |
| --- | --- | --- | --- | --- |
| Encoding catálogo | CSV catálogo | Decodificar Latin-1, delimitador `;`, parser CSV que respete quoting. No autodetección ni reparación adivinada. | Normalizar Unicode NFC. | Guardar fuente/hash; texto sospechoso se revisa, no sustituir caracteres arbitrariamente. |
| BOM/encoding pedidos | CSV pedidos | `utf-8-sig`, delimitador `,`, validar cabecera. | Quitar BOM con decoder; fallo de encoding aborta. | `INVALID_ENCODING`; no usar errors=ignore. |
| Encoding XML | Tarifas | Leer declaración UTF-8 con parser XML estándar; sin ejecutar contenido externo. | XML mal formado aborta. | `INVALID_XML`, localización del error cuando exista. |
| Cabecera distinta/incompleta | CSV | Exigir nombres/orden del contrato; sin columna extra anónima. | Abortar fuente/lote. | `INVALID_HEADER`, evitar que un cambio de esquema se trate como miles de filas inválidas. |
| Columnas de más o menos | CSV | Validar 11/9 campos; no unir sobrantes ni desplazar valores para «arreglar». | Rechazar fila. | `INVALID_COLUMN_COUNT`; conservar registro original razonablemente acotado. |
| Quoting CSV irrecuperable | CSV | Si no se pueden delimitar registros con seguridad, no continuar desde posición arbitraria. | Abortar. | `INVALID_CSV`; conservar ubicación. |
| Blancos/centinelas | Todas | Tras trim y casefold, `""`, `n/d`, `null`, `-`, `n/a` representan ausente. Solo token completo, no substring. | NULL en opcionales; rechazar obligatorios, salvo reglas específicas de descuento/cabecera. | `MISSING_REQUIRED_FIELD` con campo; un guion dentro de SKU no es nulo. |
| Textos | Catálogo/XML/pedidos | NFC, trim, colapsar espacios internos; clave de comparación casefold. No quitar tildes ni crear sinónimos no observados. | Normalizar; mantener etiqueta de presentación. | Diccionario de etiquetas de categoría/marca tomado del XML cuando hay coincidencia; otros textos conservan etiqueta del ganador. |
| SKU/id pedido/almacén | Todas | Trim, mayúsculas; no quitar guiones ni rellenar ceros; rechazar vacío, controles o longitud excesiva. | Normalizar/rechazar. | `INVALID_IDENTIFIER`; no imponer patrón PRV/PED a todos sin contrato. |
| Nombre vacío | Catálogo | Obligatorio para producto comercial. | Rechazar fila. | `MISSING_REQUIRED_FIELD`. La etiqueta de histórico solo se crea desde pedido válido. |
| Marca/categoría ausentes | Catálogo | NULL; descuento correspondiente 0 con aviso. | Aceptar con aviso. | `MISSING_PRICING_ATTRIBUTE`; categoría desconocida se muestra en grupo explícito. |
| Coma/punto decimal | Precios y pesos | Parsear texto según gramática del apartado numérico; crear Decimal directamente. | Normalizar. | Registrar original/procedencia; nunca pasar por float. |
| Moneda/miles | Precios | Permitir EUR/€ en extremo y agrupaciones inequívocas. Otra moneda o patrón ambiguo no se convierte automáticamente. | Normalizar o rechazar campo obligatorio. | `INVALID_PRICE`, `AMBIGUOUS_NUMBER`, `UNSUPPORTED_CURRENCY`. |
| Importe inválido/NaN/infinito | Catálogo, XML, pedidos | Solo Decimal finito con precisión/rango de esquema. | Rechazar fila o regla. | `INVALID_PRICE`, `NUMERIC_OUT_OF_RANGE`. No aproximar valores que desbordan BD. |
| Precio <= 0 | Coste/PVP/precio pedido/excepción | Valores monetarios requeridos estrictamente positivos. La devolución va en cantidad, no precio negativo. | Rechazar fila/regla. | `NON_POSITIVE_PRICE`. En catálogo con excepción válida, coste base ausente/inválido se descarta y audita, pero no impide usar ese neto pactado. PVP sigue siendo obligatorio. |
| PVP menor que coste | Catálogo | No corregir ni rechazar solo por margen negativo. | Avisar. | `NEGATIVE_CATALOG_MARGIN`; podría ser real. |
| EAN con espacios/comillas | Catálogo | Retirar espacios y una pareja exterior de comillas; validar dígitos, longitud EAN-8/EAN-13 y checksum. | Normalizar; si inválido, NULL con descarte de campo. | `INVALID_EAN`; EAN no es PK ni requisito de aceptar producto. |
| EAN inexistente | Catálogo | Vacío/centinela = NULL. | Conservar producto. | No inventar identificador; contar EAN ausentes en calidad. |
| EAN científico | Catálogo | Política conservadora: no reconstruir automáticamente, aunque Decimal expanda a entero; la exportación pudo perder dígitos. | NULL y descarte de campo. | `UNSAFE_SCIENTIFIC_EAN`; original disponible para recuperar solo con fuente autoritativa. |
| EAN de 12 dígitos/otra longitud | Catálogo | No prefijar cero ni confundir UPC con EAN sin contrato. | NULL y descarte de campo. | `INVALID_EAN_LENGTH`. |
| EAN repetido entre SKU | Catálogo | SKU identifica producto; EAN no tiene UNIQUE. | Conservar con aviso. | `DUPLICATE_EAN`; revisar sin fusionar productos. |
| Fecha heterogénea | CSV | Lista cerrada de formatos del apartado fechas, parsing estricto y sin fuzzy. | Normalizar/rechazar según campo. | `INVALID_DATE`. |
| Alta ausente o inválida | Catálogo | Campo no esencial: NULL si ausente; si inválido, NULL y registro. | Descartar campo inválido. | `INVALID_DATE`; no usar hoy como fecha de alta. |
| Día de pedido ausente | Pedidos | Recuperable solo de otra fila estructuralmente válida del mismo pedido, con cabecera inequívoca. | Heredar con aviso o rechazar pedido si no puede resolverse. | `HEADER_VALUE_INHERITED` / `MISSING_ORDER_DATE`. |
| Descuento heterogéneo | XML/pedidos | Convertir a ratio por regla explícita, límites [0,1]. | Normalizar/rechazar. | `INVALID_DISCOUNT`; nunca interpretar 10 como factor 10. |
| Estado/canal | Pedidos | Mapeo observado y cerrado indicado abajo. Desconocido no se convierte a completado/B2B. | Normalizar o rechazar cabecera. | `UNKNOWN_ORDER_STATUS`, `UNKNOWN_CHANNEL`. |
| Cantidad negativa | Pedidos | Entero negativo solo válido con DEVUELTO, se conserva firmado y fuera de facturación inicial. | Aceptar devolución; otros estados rechazar línea. | `INVALID_QUANTITY_FOR_STATUS`; no inferir devolución cambiando estado. |
| Cantidad positiva devuelta | Pedidos | Conservar positiva como representa el origen; fuera de facturación. | Aceptar. | No cambiar signo arbitrariamente. |
| Cantidad cero/fraccionaria/inválida | Pedidos | Unidades enteras no nulas; no redondear ni truncar. | Rechazar línea. | `INVALID_QUANTITY`. |
| Cabecera contradictoria | Pedidos | Una fecha/día, canal, estado y cliente no nulo por pedido; se admiten vacíos rellenables. | Rechazar todas las líneas del pedido si hay conflicto irresoluble. | `CONFLICTING_ORDER_HEADER`; no elegir «última» fila como si fuera cronología. |
| SKU histórico ausente | Pedido válido | Crear producto histórico solo con identidad; datos desconocidos NULL. | Conservar línea y FK. | `HISTORICAL_PRODUCT_CREATED` aviso; identificar si catálogo lo descartó. |
| SKU solo en stock | API | No crear producto comercial ni histórico exclusivamente a partir de stock. | Rechazar registro de stock. | `UNKNOWN_PRODUCT_SKU`; no rescatarlo porque se cree un histórico desde pedidos después. |
| Producto de catálogo sin stock | Cruce | Total NULL, status unknown; cero solo si se observó explícitamente suma 0. | Conservar producto. | `STOCK_NOT_OBSERVED` aviso. |
| Stock/fecha inválidos | API | Enteros quantity/reserved >=0; updated_at ISO con zona; reserved<=quantity propuesto para coherencia. | Rechazar registro y marcar total del SKU desconocido si es identificable. | `INVALID_STOCK`, `INVALID_DATE`; si ni siquiera puede atribuirse SKU, abortar snapshot por imposibilidad de valorar completitud. |
| Repetición de almacén | API | Elegir updated_at más reciente para `(sku, warehouse)`; si iguales y contenido idéntico, deduplicar; mismo instante con valores distintos invalida clave. | Auditar perdedor/deduplicado; clave contradictoria deja total del SKU NULL. | `SUPERSEDED_STOCK`, `EXACT_DUPLICATE`, `CONFLICTING_STOCK`. |
| Página/API incompleta | API | Errores de red/metadatos no son cantidades 0 ni filas descartables. | Reintentar acotadamente y abortar si no se completa. | `STOCK_FETCH_FAILED`, `INVALID_STOCK_RESPONSE`; snapshot anterior permanece. |

## Gramática numérica y redondeo

Separar `parse_decimal` de `parse_money`: peso `1.997` es un decimal de tres posiciones; un importe con un solo separador y tres dígitos a su derecha es ambiguo entre decimal y miles y se rechaza como `AMBIGUOUS_NUMBER`, salvo contrato específico documentado. No aplicar al peso la heurística de precios. Admitir signo solo donde la regla de dominio lo permita.

Ejemplos de interpretación propuesta (ilustraciones, no resultados de ETL): `30,38` y `30.38` → Decimal 30.38; `1.234,56` y `1,234.56` → 1234.56 verificando grupos de miles; `1 234,56 €` → 1234.56 si agrupación válida; `12,34,56`, `1.234` o `1,234` → ambiguo/inválido en dinero. Espacios normales o no separables se admiten como miles solo en grupos de tres; no borrar toda puntuación. Enteros como `250` son válidos. Moneda implícita EUR es S a confirmar; no hacer conversión de divisa.

No aceptar notación exponencial en importes ni porcentaje, NaN/infinito, texto residual o múltiples símbolos de moneda. XML admite decimal con punto, hasta cuatro posiciones para precios; su contrato explícito evita heurística de miles. Descuentos/pesos usan decimal sin miles. Si aparecen más decimales de los permitidos en precio de origen, rechazar para revisión; el redondeo se aplica al cálculo, no oculta pérdida de precisión del origen.

Descuento con `%`: valor dividido por 100. Sin `%`: `0 <= x < 1` es ratio, `1 <= x <= 100` son puntos porcentuales. Por tanto `10%`, `10`, `0,1` → 0.10; `1` → 0.01, `1.0` también 0.01 y `100%` → 1. No hay forma universal de resolver el 1 ambiguo: esta política es D. Vacío/centinela en descuento de línea = 0 con `DEFAULTED_DISCOUNT`; un PorcentajeBase XML ausente es regla inválida, no 0. Una regla de categoría/marca inexistente implica 0; una regla presente pero inválida no se ignora.

IVA se interpreta como puntos porcentuales (21 → 0.21), rango [0,100] antes de convertir; no aplicar el modo heurístico de descuentos. Peso debe ser >0 si está presente. IVA/peso opcionales inválidos → NULL y `INVALID_TAX`/`INVALID_WEIGHT`; las métricas no imputan IVA desconocido.

Coste neto de compra a cuatro decimales, importes y coste extendido de línea a dos, `ROUND_HALF_UP`. Descuento de línea 100% permitido (venta con importe cero); descuento combinado de compra que deje coste <=0 rechaza el producto. Cantidad × precio × descuento conserva precisión Decimal hasta ese punto. Rangos finales se comprueban antes de persistir.

## Tarifas y cruces de texto

Prioridad R: excepción SKU válida, sin otros descuentos. D: sin excepción, `coste × (1 − dc − dm)`; se elige suma por la redacción «categoría más marca», pero se deja alternativa multiplicativa en TECH_SPEC. Ejemplo ficticio: coste 100, categoría 10%, marca 5% → 85.0000 (secuencial daría 85.5000). Este ejemplo es una prueba futura, no una métrica del fichero.

Cruzar categoría/marca por NFC, espacios y casefold; no retirar acentos, cambiar nombres ni asociar marcas por similitud. Categoría/marca sin regla toma descuento 0 con `NO_MATCHING_DISCOUNT` informativo. Tarifa huérfana (excepción sin producto aceptado) se registra `UNKNOWN_PRODUCT_SKU`; no crea producto. PorVolumen, portes y plazo de pago se reconocen y quedan sin aplicar por falta de contexto de compra; registrar la política una vez por ejecución, no contarlos como fila rechazada.

Reglas XML idénticas de la misma clave: colapsar y registrar duplicado. Valores contradictorios: `CONFLICTING_TARIFF`, invalidar esa clave y rechazar los productos que dependan de ella. Una excepción SKU presente pero inválida no puede caer silenciosamente al precio general: rechazar ese producto con `INVALID_SKU_EXCEPTION`. Una excepción válida puede prescindir de coste base inválido, pero conserva el descarte de ese campo. Identificar reglas por ruta del nodo y ordinal, no inventar número de línea XML.

## Duplicados deterministas

1. Filas exactamente iguales tras parsing se colapsan por fuente, conservando el menor ordinal; cada ocurrencia descartada tiene `EXACT_DUPLICATE` y referencia al ganador. No eliminar filas válidas porque otra fila inválida sea parecida.
2. Para catálogo, agrupar por SKU normalizado después de validaciones esenciales y pricing. Si valores normalizados coinciden, es duplicado semántico (`NORMALIZED_DUPLICATE`). Si difieren, seleccionar menor número de campos opcionales descartados, luego mayor completitud de opcionales y finalmente menor ordinal físico. Fecha_alta no es fecha de actualización. Registrar cada candidato descartado como `CONFLICTING_PRODUCT_SKU` con criterio y ganador. Si ninguna fila es válida, no cargar producto comercial. Ordenar/reformatear el fichero puede cambiar un empate: es limitación declarada, no se presume historial de modificaciones.
3. Para pedidos, agrupar por id_pedido y resolver cabecera primero. Nunca colapsar todas las líneas por SKU: pueden tener distintos precios/descuentos. Dedupe por firma `(id_pedido, sku, cantidad, precio_unitario, descuento_linea)` canónica, conservando primer localizador. Distintas firmas se conservan. Registrar los descartes como `DUPLICATE_ORDER_LINE` y mostrar impacto de esta hipótesis en F6.
4. Serialización de firma determinista, con nombres/orden, versión y decimales canónicos (sin diferencias entre 10 y 10.00); usar SHA-256, no `hash()` de Python. Una improbable colisión con payload distinto se trata como fallo, nunca como deduplicación.
5. Al reimportar un CSV completo, sincronizar al conjunto actual de firmas. No acumular líneas antiguas corregidas; estrategia transaccional en TECH_SPEC. Si el origen fuera incremental, esta regla no sería válida y habría que rediseñar con ID estable.

## Fechas y cabeceras

Formatos permitidos inicialmente: `%Y-%m-%d`, `%d/%m/%Y`, `%d-%m-%Y`, `%Y/%m/%d`, y esas fechas con ` HH:MM:SS`; ISO con `T`, segundos y offset/Z para timestamps de API. Probar años bisiestos y rechazar imposibles, fechas numéricas ambiguas fuera de esa lista y timestamps sin zona en stock. No interpretar mes/día americano.

En pedidos conservar **día**: la muestra representa un mismo pedido con hora y sin ella, no hay hora canónica fiable. Una fecha con offset se convierte primero a zona de negocio; una fecha/hora local sin offset se interpreta en zona configurada, pendiente de confirmar. `fecha_alta` también se almacena como día. La API y los runs guardan instante UTC. Fecha de pedido futura: conservar y advertir `FUTURE_ORDER_DATE`, excluir de consultas hasta `as_of`; no cambiarla por hoy.

Para una cabecera, comparar solo valores normalizados no nulos de filas estructuralmente válidas. Fecha/estado/canal vacíos pueden heredarse si hay exactamente un valor canónico; cliente puede ser NULL si todas las filas lo omiten. Un valor no vacío inválido de cabecera o dos valores incompatibles rechazan el pedido completo; no «arreglar» la fecha inválida con otra fila. Registrar el motivo para cada localizador afectado. Variación solo de capitalización/espacios de cliente no genera conflicto. La herencia de cabecera no repara un precio unitario ni cantidad ausente de la línea.

Si cabecera válida pero algunas líneas fallan, cargar las válidas y marcar `has_rejected_lines=true`; pedido sin líneas válidas no se publica (`ORDER_WITHOUT_VALID_LINES`). Informar en dashboard y resumen la existencia de pedidos parciales para evitar presentar totales incompletos como conciliación contable exacta.

## Estados, canales y facturación

Etiquetas observadas de estado: `CANCELADO`, `COMPLETADO`, `Completado`, `DEVUELTO`, `ENVIADO`, `PENDIENTE`, `cancelado`, `completado`, `enviado`. No se han inventado estados adicionales.

| Comparación tras trim/casefold | Canónico | Facturación propuesta |
| --- | --- | --- |
| completado | COMPLETADO | Sí, líneas válidas positivas. |
| enviado | ENVIADO | Sí, aproximación operativa de venta entregada a transporte. |
| pendiente | PENDIENTE | No: no se ha materializado la venta según esta política. |
| cancelado | CANCELADO | No. |
| devuelto | DEVUELTO | No: falta información para asociar y periodificar el abono. |

Etiquetas de canal observadas: `B2B`, `B2C`, `MARKETPLACE`, `Marketplace`, `b2b`, `b2c`. Canónicos: `B2B`, `B2C`, `marketplace`. Mapeo casefold exacto; desconocidos se rechazan. Esta representación debe ser idéntica en DB, SQL, dashboard y Make.

La elección de enviados/completados y exclusión de devueltos es D/S, no instrucción del README. Se debe comunicar como facturación operativa de registros aceptados, con política visible. Todas las estadísticas parten del mismo conjunto y JOIN real a productos. Margen usa coste actual conocido; históricos sin coste contribuyen a ventas pero no al subtotal de margen conocido. Fórmulas/ventanas en TECH_SPEC.

## Stock y ausencia de SKU

Una observación válida con quantity 0 es evidencia de cero para ese almacén; ausencia de observación no lo es. D: asumir que una instantánea completa contiene todos los almacenes con información del proveedor; es S que debe validarse. Sumar almacenes conocidos de un SKU solo si no tiene observaciones inválidas/conflictivas. Si alguna impide conocer el total, mantener las observaciones válidas para auditoría pero publicar `stock_total=NULL, stock_status=invalid`, no una suma parcial. Sin observaciones: `stock_status=unknown`. Con conjunto íntegro: `stock_status=known` y suma, incluida 0.

Unknown SKU de stock no se convierte en histórico; un histórico existe por una línea de pedido válida. Stock obsoleto no se transforma en cero: mostrar fecha/antigüedad, umbral de aviso pendiente de negocio. No rechazar por antigüedad arbitraria. `reserved > quantity` se considera inválido por decisión conservadora a confirmar; alternativa sería disponibilidad negativa con aviso si el proveedor permite sobreventa.

## Contrato de rechazos y reconciliación de conteos

Cada incidencia tendrá `run_id`, fuente, `record_locator`, entidad/clave si se conoce, `reason_code`, `field_name`, severidad, acción, detalle, payload original razonable y referencia al ganador si procede. CSV: ordinal de registro (cabecera = 1) y líneas físicas inicial/final, porque un campo quoted puede contener saltos. XML: ruta de nodo y ordinal. API: página e índice más SKU/almacén/updated_at si existen.

Payload acotado (propuesta 8 KiB configurable), flag de truncamiento y hash; no tokens, Authorization, DSNs ni URL de Make. Acceso local restringido a la BD; datos de cliente no se copian a capturas o fixtures públicas. Fuente estructuralmente ilegible: incidencia con localizador de fuente/error, no fila inventada.

`reason_code` es estable y comprobable en tests, los detalles pueden cambiar. Los códigos de la matriz y secciones son el catálogo inicial; los fallos inesperados usan `UNEXPECTED_ERROR` con error saneado y run fallido, no «fila inválida» genérica. No capturar excepciones para seguir como éxito.

Contadores por fuente: registros leídos = aceptados + duplicados descartados + otros rechazados, asignando **una sola disposición final por registro**. Un campo descartado/aviso puede acompañar un aceptado. Una fila con varios errores cuenta una vez en `rejected_rows` y una vez por motivo distinto en distribución de motivos; por eso sumar motivos puede superar rejected_rows. Duplicados cuentan como filas descartadas y forman parte de rejected_rows para Make, con desglose separado. Registros sintéticos históricos no son filas de catálogo aceptadas. Reglas XML ignoradas por alcance se cuentan como reconocidas/no aplicadas, no se mezclan en la reconciliación de filas de productos.

Métricas de inserción/actualización/sin cambio se calculan comparando valores de negocio, no por affected_rows ni timestamps MySQL. Rejections de cada run permanecen: repetir el ETL aumenta auditoría, no duplica negocio. Comparar tanto el conjunto final como las incidencias normalizadas entre runs con entradas congeladas.
