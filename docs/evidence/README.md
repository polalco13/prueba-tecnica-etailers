# Evidencia visual de F9

Capturas reales del navegador local el 25/09/2026, sin recrear ni retocar datos:

- [Panel y gráfico](f9-dashboard.png): facturación/unidades mensuales, KPIs y avisos.
- [Catálogo con filtros combinados](f9-catalog-filter.png): búsqueda `destornillador` y categoría `Herramienta manual`; cuatro resultados, incluido stock desconocido.

Origen: las cuatro fuentes originales de la prueba, cargadas en MySQL 8.0.46 temporal, BD `f4_test_web_real`, run `76173378-fc01-4c34-b36b-7b45fda9ad58`, completado a las 10:52 UTC. Fecha analítica: 25/09/2026 en Europe/Madrid. No son fixtures sintéticas ni una carga en el volumen del usuario. Capturas limitadas a productos y agregados, sin clientes, tokens ni credenciales.

Se comprobó en navegador: gráfico con ejes de importe/unidades y 18 meses; tabla desplegable con valores exactos; búsqueda y categoría juntas; limpieza y paso de página 1 a 2; etiquetas de histórico, stock desconocido y margen negativo. A 390 × 844 se detectó/corrigió el desbordamiento de tablas y se verificó que la página no ensancha el viewport (las tablas tienen desplazamiento propio). Los dos scripts se sirven desde localhost; no se observaron errores ni avisos en la consola JavaScript. Se restauró el tamaño normal al terminar.

Verificación automatizada separada: 348 pruebas pasan (307 sin BD y 41 MySQL), incluidas nueve pruebas de F9 con datos sintéticos y fecha fija; Ruff y formato correctos. Starlette emite una deprecación por TestClient/httpx, documentada sin ocultarla en [SOLUCION](../../SOLUCION.md#dashboard-f9-y-comprobación-manual).

Las cifras, ejecución y pasos para reproducirlas se describen en [SOLUCION](../../SOLUCION.md). Las imágenes acreditan el estado observado, no confirman la validez comercial de los costes, EUR o IVA. El servidor y MySQL temporales se retiraron tras las comprobaciones. F10 no se ha iniciado.
