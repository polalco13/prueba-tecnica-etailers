# Validación final — 28/09/2026

Clon nuevo de GitHub `main` (`aab89b9`), venv nuevo y MySQL aislado; Python 3.13.13, Compose 2.38.2 y MySQL 8.0.46. Instalación, `pip check`, migraciones 001–004 y arranque verificados. Make desactivado durante esta comprobación.

- Dos cargas originales con fecha analítica fija 2026-09-28: mismos valores de negocio, fuentes sin cambios y auditoría adicional esperada.
- 159 productos (115 comerciales + 44 históricos), 358 pedidos y 1.101 líneas; FKs, claves únicas y contadores sin discrepancias.
- Recálculo independiente con Decimal coincidente con SQL en facturación, pedidos, margen y serie mensual; canales/categorías suman el total.
- **397 tests aprobados**, ninguno omitido (347 sin BD + 50 MySQL); Ruff y formato correctos. Deprecación Starlette/TestClient conocida.
- Navegador: gráfico dibujado, filtros combinados, limpiar y paginación correctos; consola sin errores observados.
- Revisión acotada de patrones de secretos en historial/árbol de trabajo y del blueprint/capturas: sin hallazgos; no equivale a certificación exhaustiva.

[Reporte de las dos cargas](repeatability.json) · [Procedimiento reproducible](../../validation/README.md) · [Capturas de entrega](../README.md).

La prueba MySQL y la web temporal se retiraron sin tocar los servicios/datos del usuario. Make se acredita por separado con la ejecución real del 27/09/2026 y sus [límites](../../../make/README.md#cierre-y-límites-de-verificación). La revisión responsive está en [F10b](../f10b/README.md).

GitHub público y seis PR integradas a `main` verificados. **Pendiente:** integrar la documentación F12 y enviar el [correo preparado](../../delivery/email.md). No se identifica implementación obligatoria pendiente; los supuestos comerciales y extras siguen explícitos en [SOLUCION](../../../SOLUCION.md).
