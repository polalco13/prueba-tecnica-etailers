# Validación de la corrección final — 29/09/2026

Código funcional `7fdaeac`, reglas `catalog-stock-orders-v3`, Python 3.13.13 y MySQL 8.0.46. Se reutilizó el entorno temporal de [validación](../../validation/README.md), sin volúmenes ni BD del usuario. Fecha analítica fija **2026-09-28**; Make desactivado. Baseline v2 generado en f12_real y corrección en f13_real, con idénticos hashes de CSV/XML/stock.

| Resultado | Antes (v2) | Después (v3) |
| --- | ---: | ---: |
| Comerciales / históricos | 115 / 44 | 120 / 39 |
| Pedidos / líneas | 358 / 1.101 | 358 / 1.101 |
| Facturación | 1.381.450,43 | 1.381.450,43 |
| Margen conocido | −2.954.287,69 | 575.355,92 |
| Ventas con coste | 1.248.262,11 | 1.319.415,62 |
| Cobertura | 90,36 % | 95,51 % |

Dos cargas corregidas dejaron idéntico negocio y nueva auditoría. FKs/UNIQUE, contadores por fuente y suma de stock comprobados. Catálogo: 133 leídas = 120 aceptadas + 10 rechazadas + 3 deduplicadas; stock: 230 = 216 + 14; pedidos: 1.142 = 1.101 + 33 + 8. Disminuye el rechazo de stock al recuperar catálogo. Bajo mínimos sigue en 12.

[Reporte reproducible](repeatability.json) y [comparación por SKU](comparison.json). Recálculo independiente Decimal desde líneas coincide con SQL; facturación/pedidos/ticket y todos los meses coinciden antes/después. Las cinco recuperaciones y las ventas de PRV-2013/2061 permanecen incluidas.

Muestra manual: PRV-2013 toma catálogo fila 109: `318.52 × (1−0.10−0.08) = 261.1864`. Pedido fila 345: venta 1.019,58, coste extendido 522,37, margen 497,21. PRV-2061: `23.45 × 0.89 = 20.8705`; pedido fila 35, venta 46,29, coste 20,87 y margen 25,42. Se conserva el CSV y se auditan filas 97/23 rechazadas. PRV-2104 mantiene el primer coste plausible, con conflicto visible.

**443 tests pasan (392 sin BD + 51 MySQL), ninguno omitido**, incluidos selección, normalización/auditoría, históricos/promoción, rollback e idempotencia. Ruff y formato correctos. Aviso de deprecación Starlette/TestClient conocido; no se añadió otro cliente HTTP para silenciarlo.

Documentación propia: 9.989 palabras frente a 22.050, reducción del 54,70 %. SOLUCION queda en 905 palabras; enlaces locales y anclas comprobados. Conteo según la guía de fase, incluidos documentos nuevos.

Navegador (captura directa 1440×1200): margen/cobertura y aviso coherentes; gráfico, tabla mensual, filtros combinados, limpiar y paginación revisados con las fuentes reales mediante teclado; consola sin errores/avisos observados. [Captura actual](../dashboard.jpg). Esta comprobación no repite la auditoría responsive previa ni certifica accesibilidad completa.

Make conserva la evidencia externa de 27/09/2026 y sus [límites](../../../make/README.md#cierre-y-límites-de-verificación). Los tres JSON son campos distintos, no tres transformaciones del mismo valor; consolidación/nombre de escenario no modificados en cuenta. Ninguna notificación enviada en F13. Base fiscal y costes históricos siguen sin confirmar comercialmente.
