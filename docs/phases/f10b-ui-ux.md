# Mejora de lectura y uso del panel

Fase F10b integrada en la PR 6 (`aab89b9`). Ampliación visual solicitada después de Make; no modifica ETL, métricas, fuentes ni configuración. [Evidencia histórica](../evidence/f10b/README.md).

Se conservó FastAPI/Jinja2, CSS/JS nativos y Chart.js local. Los cambios priorizaron periodo/publicación/KPIs, accesos a evolución/inventario/catálogo, cifras alineadas, tabla mensual de respaldo, filtros activos, limpiar y paginación. Las tablas anchas se desplazan dentro de su región en móvil; controles tienen etiquetas y foco, y el movimiento respeta preferencias reducidas.

Criterios comprobados: todas las estadísticas/columnas del enunciado disponibles; cifras iguales antes/después sobre la misma publicación; búsqueda y categoría combinables; página sin desbordamiento global en escritorio/móvil; teclado, vacíos/errores y distinción de stock desconocido/cero, históricos, parciales y cobertura. No se creó una SPA, una nueva métrica ni un build.

Las skills impeccable, emil-design-eng y referencias frontend-ui-ux-design guiaron la revisión. La evidencia recoge la verificación acotada, sin atribuirle una auditoría WCAG completa. Comparativas antiguas en Git; la captura actual de entrega está en [evidencias](../evidence/README.md).
