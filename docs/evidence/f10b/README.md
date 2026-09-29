# Revisión visual histórica — 28/09/2026

F10b usó la publicación real `c1a93f67-6990-4748-8efa-c18bc6777b42`, fecha analítica 28/09/2026 y filtro destornillador/Herramienta manual. Comparativas originales en Git; la [captura de entrega](../dashboard.jpg) se actualiza con la validación más reciente.

| Antes | Después | Motivo |
| --- | --- | --- |
| Contexto ocupaba la primera vista y navegación limitada. | Periodo/KPIs priorizados, accesos a secciones y detalles secundarios desplegables. | Facilitar lectura y recorrido. |
| Tablas anchas sin indicación móvil. | Regiones desplazables, foco y primera columna fija. | Conservar columnas sin desbordar página. |
| Estado de filtros poco visible. | Filtros activos, limpiar y paginación persistente. | Mantener contexto de búsqueda. |

Se revisaron 1440×900 y 390×844, teclado, texto al 200 %, tabla con scripts bloqueados y consola. DOM de KPIs/serie/tablas coincidente antes/después; 9 tests web MySQL, Ruff/formato y `node --check` correctos. Revisión acotada, no auditoría WCAG. Sin ETL, Make/correo, modificaciones de fuentes ni `.env` en esa fase.
