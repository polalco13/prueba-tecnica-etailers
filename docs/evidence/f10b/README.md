# Evidencia F10b — mejora UI/UX

La evidencia se capturó en la web ejecutable local (`http://127.0.0.1:8000/`) con la publicación real `c1a93f67-6990-4748-8efa-c18bc6777b42`, finalizada el 27/09/2026 a las 15:34 UTC. Se mantuvo `as_of=28/09/2026`, zona `Europe/Madrid` y, para el catálogo, la búsqueda `destornillador` con categoría `Herramienta manual`.

Las capturas antes/después y el detalle de comparación se retiraron del paquete final para simplificarlo; están en el historial Git. Se conserva la [captura de entrega](../dashboard.png), tomada después sobre el clon limpio F12.

## Revisión Before | After | Why

| Before | After | Why |
| --- | --- | --- |
| Navegación limitada a Resumen/Catálogo y varios textos de contexto ocupaban el primer pantallazo. | Cabecera fija con Resumen, Evolución, Inventario y Catálogo; criterios secundarios en `<details>` y el supuesto EUR/IVA visible junto a los KPIs. | Permite saltar entre tareas y deja la limitación económica cerca de las cifras que condiciona. |
| Las tarjetas usaban borde de color, tipografía más pequeña y el margen no tenía acceso directo a su detalle. | Jerarquía tipográfica en rem, tarjeta de facturación priorizada, margen con enlace a Cobertura y estados negativos/pendientes conservados. | Mejora el escaneo sin presentar el margen como beneficio definitivo. |
| La fecha de última carga aparecía como texto aislado. | La publicación disponible/sin publicación tiene un estado compacto y semántico junto a la fecha. | Permite saber de un vistazo si las cifras proceden de una publicación disponible sin convertirlo en una decoración. |
| El gráfico quedaba muy abajo y su fallback no tenía una tabla desplegable claramente asociada. | Evolución sube en la jerarquía, el gráfico distingue barras/línea y la tabla exacta sigue siendo nativa y usable sin JavaScript. | Hace visible el análisis temporal y mantiene la fuente verificable de importes. |
| En móvil las tablas anchas no indicaban cómo ver precios, stock o columnas secundarias. | Regiones desplazables con foco, pista de desplazamiento y primera columna del catálogo fijada en móvil. | Conserva todas las columnas sin desbordar la página. |
| Filtros y paginación funcionaban, pero el estado activo no se explicaba después de navegar. | Formulario etiquetado, acción Limpiar, filtros activos y enlaces anterior/siguiente siempre comprensibles; los filtros continúan solo en catálogo. | Reduce la incertidumbre y mantiene la búsqueda al cambiar de página. |

## Comprobaciones realizadas

- Escritorio: 1440 × 900. Móvil: 390 × 844. No hubo desbordamiento de la página en las vistas ejecutables.
- Comparación DOM de la misma publicación: cuatro KPIs, serie mensual de 18 meses y celdas de seis tablas coinciden.
- Recorrido del navegador: evolución, tabla mensual, foco de región, búsqueda + categoría, Limpiar y paginación; la paginación mantuvo `q` y `category`.
- Tabla sin JavaScript: una previsualización local de solo lectura aplicó CSP `script-src 'none'`; se conservaron 18 filas mensuales y los seis cuadros tabulares, y el `<details>` siguió funcionando.
- Texto ampliado: una previsualización local aplicó 200 % al documento; la navegación se ajustó sin desbordar el viewport. Las tablas anchas se desplazan dentro de su contenedor.
- Pulido final: estado de publicación, radios de superficie consistentes y feedback de pulsación; el movimiento se desactiva con `prefers-reduced-motion`.
- Consola del navegador sin errores/avisos observados. `node --check src/web/static/dashboard.js` pasó.
- Regresión web sobre MySQL 8.0.46 temporal sin volumen del usuario: `9 passed` (`tests/integration/test_web.py`). También pasaron `ruff check src tests`, `ruff format --check src tests` y `git diff --check`.

La revisión es una comprobación acotada de F10b, no una auditoría completa WCAG. No se ejecutó ETL, Make, correo ni se modificaron las fuentes originales o `.env`.
