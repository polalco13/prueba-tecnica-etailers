# Alcance de la solución

El [README](README.md) contiene el enunciado. Este documento resume el alcance; las reglas aplicadas están en [DATA_RULES](DATA_RULES.md), la arquitectura en [TECH_SPEC](TECH_SPEC.md) y el arranque/resultados en [SOLUCION](SOLUCION.md).

El cliente necesita integrar catálogo CSV, tarifas XML, pedidos CSV y stock REST en MySQL, consultar el negocio y recibir avisos útiles. La entrega conserva los datos originales, la procedencia de los descartes y relaciones reales entre pedidos y productos.

| Necesidad | Resultado |
| --- | --- |
| Integración de cuatro fuentes | Comando ETL con normalización, rechazos y publicación transaccional. Una extracción incompleta conserva la publicación anterior. |
| Catálogo y precio de compra | Excepción XML prioritaria; descuentos de categoría/marca en los demás casos. Búsqueda, categoría y stock conocido/desconocido. |
| Histórico relacionado | Cabeceras y líneas con FKs; productos históricos mínimos para SKUs ausentes o rechazados. |
| Análisis | Evolución mensual desde abril de 2025, facturación/pedidos/ticket, canales, categorías, top 10, margen/cobertura y bajo stock con ventas recientes. |
| Make | Resumen persistido, webhook, filtros, histórico en Sheets y alerta Gmail condicional. Blueprint y captura auténticos. |
| Repetibilidad | Mismas fuentes/reglas dejan idéntico negocio. Cada ejecución añade auditoría. |
| Entrega | Guía desde cero, decisiones, límites, explicación de escala, capturas y trabajo Git por incrementos. |

La corrección final solicitada el 29/09/2026 valida el coste neto frente al PVP antes de resolver duplicados y recupera el sufijo monetario degradado del catálogo. La mejora visual previa conserva FastAPI/Jinja2 y las métricas. [Plan y estado](IMPLEMENTATION_PLAN.md).

La aceptación exige números reconciliados con un cálculo independiente, FKs/rollback/repetibilidad comprobados en MySQL y lectura comprensible del panel. Los resultados técnicos no confirman supuestos comerciales: moneda/base fiscal, descuentos aditivos, stock físico, coste actual y facturación de enviados/completados siguen explícitos.

Quedan fuera autenticación multiusuario, edición de datos, ERP/contabilidad completos y nuevas fuentes comerciales. Incremental, contenedor Python y comparativa anual son opcionales no implementados. No se inventan EAN, costes históricos ni vínculos de devolución. El envío de entrega requiere instrucción explícita; su estado no se deduce de una rama fusionada.
