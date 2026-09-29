# Reglas de datos aplicadas

Versión actual: **`catalog-stock-orders-v3`**, corrección final autorizada el 29/09/2026. El [README](README.md) exige decidir/documentar el tratamiento de datos sucios; estas son las decisiones del ejercicio, con los supuestos comerciales indicados al final. Implementación: [TECH_SPEC](TECH_SPEC.md); resultados: [SOLUCION](SOLUCION.md).

## Acciones y procedencia

Normalizar conserva significado; rechazar fila excluye entidad; descartar campo conserva entidad con NULL; deduplicar conserva una ocurrencia; avisar conserva el dato; fallar ejecución impide publicar. Todo descarte/corrección registrado conserva run, fuente, fila/localizador, entidad, motivo/campo, acción y extracto original limitado. No guardar secretos ni imprimir clientes/payloads sensibles. Desconocido significa NULL, nunca cero.

## Catálogo y tarifas

Catálogo Latin-1 con `;`, lector CSV real y 11 columnas: SKU, EAN, nombre, marca, categoría, coste, PVP, IVA, peso, alta, descripción. Comillas y campos multilínea respetados. Cabecera/archivo ilegible → ejecución fallida; columnas incorrectas → fila rechazada. No desplazar campos ni modificar `data/`.

| Caso | Regla |
| --- | --- |
| Vacíos | Tras trim/casefold, solo tokens completos `N/D`, `NULL`, `-`, `n/a` o vacío son ausencia. SKU/nombre/marca/categoría/PVP son obligatorios; descripción y otros atributos opcionales admiten NULL. |
| Texto/identificadores | NFC, trim y espacios; claves de marca/categoría comparan mayúsculas conservando tildes. SKU/ID en mayúsculas, sin quitar guiones/rellenar ceros, máximo 64 y sin controles. No truncar. |
| Dinero | Decimal desde texto; coma/punto decimal, € o EUR y miles inequívocos. `1.234,56` → 1234.56; `1.234` aislado es ambiguo. Sin exponentes, no finitos, cero/negativos ni desbordamiento DECIMAL(18,4). |
| Moneda degradada | Solo coste/PVP de este CSV: un único `?` final se admite si el resto pasa la gramática. `60,56?` → 60.56; incidencia `NORMALIZED_CURRENCY_SUFFIX`, acción normalize/info, original conservado. `?60,56`, `60?56`, `60,56??`, `?` se rechazan; `1.234?` sigue ambiguo. No relajar otros parsers. |
| EAN | Limpiar espacios/comillas exteriores o apóstrofo Excel inicial; validar EAN-8/13 y checksum. Vacío → NULL; inválido/científico → campo descartado con motivo. No reconstruir dígitos/ceros perdidos. |
| IVA/peso/alta | Opcionales: inválidos → NULL con incidencia. IVA usa ratio; peso decimal sin miles, cero válido, negativo inválido. Alta estricta sin fecha inventada. |
| Coste CSV inválido | Candidato condicionado: solo una excepción XML válida puede proporcionar precio neto. Con excepción, auditar descarte del coste original; sin ella, rechazar fila. |
| XML | UTF-8, secciones Descuentos/Excepciones identificables, sin DOCTYPE. Ilegible, regla general inválida o misma clave con tarifas contradictorias → falla ejecución. Regla repetida idéntica → deduplicación. |
| Prioridad | Excepción SKU manda sin descuentos adicionales. Ausente: `coste × (1 − descuento categoría − descuento marca)`. Descuentos ausentes = 0; suma ≥1 o neto redondeado ≤0 rechaza producto. Excepción inválida o flag adicional distinto de false rechaza producto, sin fallback. |
| Calidad de coste | Después del neto/redondeo, rechazar candidato con `net_cost > pvp`: `COST_EXCEEDS_PVP`, auditando neto/PVP/origen/fila. Igualdad permitida. Se comprueba también la excepción XML; no elegir otra tarifa para ocultar el problema. No prohíbe una venta real por debajo del coste. |
| Duplicados SKU | Validar cada candidato antes de escoger. Entre válidos, primero del archivo; los demás quedan auditados. Exactamente iguales en las 11 celdas → EXACT_DUPLICATE; diferentes → CONFLICTING_PRODUCT_SKU, con fila conservada. Orden determinista, sin afirmar actualidad comercial. |

Los descuentos son aditivos por decisión del ejercicio: coste 100, 10% y 5% → 85 (secuenciales darían 85.5). No aplicar PorVolumen sin compras conocidas, portes ni plazo de pago; términos reconocidos con aviso. Excepción sin candidato de catálogo: aviso UNKNOWN_PRODUCT_SKU, sin crear producto.

La recuperación de `?` corresponde al patrón de símbolo monetario degradado observado: el archivo contiene ya ese carácter literal, cambiar la decodificación no reconstruye el original. La validación coste/PVP es conservadora bajo el supuesto de base fiscal comparable; no certifica un precio comercial.

## Pedidos

UTF-8 con BOM, separador coma, 9 columnas y lector con comillas: ID, fecha, cliente, canal, estado, SKU, cantidad, precio y descuento. Agrupar por ID normalizado. Fecha estricta acepta ISO, dd/mm/yyyy, dd-mm-yyyy, yyyy/mm/dd y hora si existe; agrupar por día. Hora y fecha sin hora del mismo día son compatibles.

Cabecera: vacíos heredan solo un valor inequívoco del mismo grupo con HEADER_VALUE_INHERITED. Cliente puede quedar NULL; comparar NFC/espacios/casefold y conservar primera grafía válida no vacía. Variantes de mayúsculas fueron confirmadas por el usuario; no unir tildes, puntuación o nombres parecidos. Valor no vacío inválido no se oculta mediante herencia. Conflicto real rechaza pedido/líneas; fecha sin día recuperable también. Una línea inválida no elimina hermanas: pedido parcial si quedan válidas; sin líneas no se carga. Archivo vacío/ilegible/sin pedidos válidos aborta publicación.

Estados canónicos: ENVIADO, COMPLETADO, PENDIENTE, CANCELADO, DEVUELTO. Canales: B2B, B2C, marketplace, sin distinguir mayúsculas. Desconocidos rechazan cabecera, sin correspondencias aproximadas. Cantidad entera exacta distinta de cero: `2,0`/`2.0` → 2; fracciones/desbordamiento se rechazan. Negativas solo en DEVUELTO, conservando signo. Precio unitario positivo obligatorio.

Descuentos: `10%`, `10`, `0,1` → 0.10. Con `%`, dividir por 100; sin él, [0,1) es ratio y [1,100] puntos porcentuales (`1` → 1%). Ratio final [0,1], hasta seis decimales; vacío → cero con aviso. No reparar sufijos monetarios del catálogo en pedidos/XML, cantidades, descuentos o EAN.

Firma `order-line-v1`: SHA-256 de pedido/SKU/cantidad/precio/descuento canónicos, sin fila física. Repetidas por firma se deduplican y auditan; dos líneas legítimas iguales son indistinguibles sin ID ERP. La corrección de cliente produjo v2; las reglas de catálogo producen v3 sin cambiar firma ni estados elegibles.

SKU válido de pedido sin catálogo aceptado crea/reutiliza histórico mínimo: comercial false, histórico true, costes/PVP/stock NULL. Conservar ventas/FKs. Registrar HISTORICAL_PRODUCT_CREATED solo al crear efectivamente; distinguir SKU ausente de catálogo rechazado. Si regresa al catálogo, promocionar mismo ID. Stock o líneas rechazadas no crean históricos. [ADR 002/003](docs/adr/README.md).

## Stock

API completa, todas las páginas y reintentos acotados. Extracción incompleta → STOCK_FETCH_FAILED y ningún cambio publicado. Un SKU solo en API no crea producto; observación rechazada UNKNOWN_PRODUCT_SKU.

Cantidad/reserva: enteros exactos de 0 al máximo BIGINT firmado, sin booleanos/ausentes/fracciones. Fecha con zona, convertible a UTC/DATETIME; inválida rechaza observación. `reserved > quantity` avisa y conserva ambas; no se resta para calcular stock físico.

Clave SKU/almacén: repeticiones normalizadas iguales → EXACT_DUPLICATE; versiones antiguas → SUPERSEDED_STOCK, ambas deduplicadas. Elegir actualización más reciente. Valores contradictorios al mismo instante rechazan observaciones e invalidan el total del SKU, aunque haya otra versión posterior; no recuperar arbitrariamente una anterior.

Conservar almacenes válidos aunque alguno falle; total/fecha NULL y estado invalid evita suma parcial. Sin observaciones: unknown y total NULL. Solo conjunto válido completo: known, suma quantity, incluido cero real. Suma desbordada: aviso NUMERIC_OUT_OF_RANGE y total inválido. `stock_as_of` es fecha máxima aceptada, no frescura común garantizada.

## Métricas, carga y conteos

Facturación operativa: ENVIADO/COMPLETADO, líneas positivas aceptadas, desde 01/04/2025 hasta `as_of` inclusivo. Excluir pendientes/cancelados/devueltos. Conservar devoluciones sin compensarlas automáticamente: falta vínculo con venta original. Parciales aportan solo líneas aceptadas.

Neto unitario a cuatro decimales; importe y coste extendido de línea a dos con ROUND_HALF_UP antes de sumar. Importe = cantidad × precio pedido × (1−descuento). Margen conocido = importe − cantidad × neto actual redondeado. Coste NULL no es gratis: ventas sin coste aparte y cobertura = ventas con coste / total (NULL si total cero). Margen negativo legítimo se conserva. Ticket = ventas/pedidos distintos elegibles, NULL sin pedidos.

Canales/categorías reconcilian con total; histórico sin categoría tiene grupo explícito. Top 10 por facturación descendente y SKU ascendente en empates. Completar todos los meses desde abril de 2025 con cero real; mes actual parcial. Bajo stock: vigente, físico conocido <5 y venta elegible en ventana inclusiva de tres meses naturales, ajustando día al último válido. Make usa mes anterior completo y esa misma consulta de bajo stock.

Publicar instantáneas completas atómicamente, con reconciliación y un escritor; no TRUNCATE ni FKs desactivadas. Fuente cambiada durante lectura, snapshot vacío, MySQL/fallo inesperado → abortar con motivo saneado. Mismo input/reglas conserva negocio; auditoría/timestamps crecen.

Por fuente completada: `leídas = aceptadas + rechazadas + deduplicadas`. Una fila rechazada cuenta una vez aunque tenga varios motivos; los motivos pueden sumar más que filas. Avisos, campos descartados y normalizaciones no inflan rechazos. Resumen Make solo para completed, persistido al publicar: alerta si filas rechazadas > umbral o hay bajo stock. Fallos completos siguen failed en auditoría local; no enviar ventas viejas con éxito ficticio.

Supuestos pendientes de confirmación comercial: EUR/base fiscal comparable, coste actual como estimación histórica, descuentos aditivos, stock físico sin reservas, Europe/Madrid y autoridad de futuras exportaciones/identidad de línea ERP. No son resultados de pruebas técnicas.
