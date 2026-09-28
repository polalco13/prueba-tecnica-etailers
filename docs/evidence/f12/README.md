# F12 — validación de entrega, 28/09/2026

**Resultado:** implementación documental y validación local terminadas en `feature/delivery-docs`. El código funcional `aab89b9` ya está en `main` (PR 6). Queda integrar F12 para que el paquete documental final esté en `main`, y enviar el correo por instrucción explícita del autor. No se ha ejecutado F11 ni se han cambiado reglas de negocio.

## Alcance identificado antes del cambio

| Archivos | Razón | Criterio de aceptación |
| --- | --- | --- |
| SOLUCION, PRD, TECH_SPEC, DATA_RULES, IMPLEMENTATION_PLAN, estado Make/ADR | Había instrucciones incompletas y estados previos a PR 5/6 | Arranque ejecutable, reglas coincidentes con código, sin TBD de implementación obligatoria; propuestas comerciales diferenciadas |
| `docs/validation/` y esta carpeta | Reproducibilidad desde clon/BD nuevos | Instalación limpia, cuatro migraciones, dos cargas originales idénticas y suite MySQL completa; evidencia fechada |
| `docs/delivery/` | Preparar defensa y entrega | Recorrido origen → rechazo/métrica, puntos de cambio, correo de 2–3 párrafos con enlace/adjuntos; sin enviar |
| `.gitignore` y metadatos Finder seguidos | Excluir artefactos locales | Ignorar y dejar de versionar `.DS_Store`, preservando las copias locales y cambios previos |

No se modifican `src/`, `tests/`, migraciones, originales de `data/`, mock, blueprint ni dependencias. La validación usa servicios separados y no el volumen del usuario.

## Entorno y ejecución real

Clon nuevo desde el repositorio público, Python 3.13.13 en venv nuevo, Docker 29.2.1, Compose 2.38.2, MySQL 8.0.46. El harness F12 se copió al clon; la aplicación procede íntegramente del main `aab89b9`. MySQL temporal `nortesur-f12-mysql`, base `f12_real`, puerto 13317, almacenamiento tmpfs; mock original en 13311. Instalación sin incompatibilidades (`pip check`); migraciones 001–004 aplicadas y segunda invocación sin cambios. Make desactivado, **cero solicitudes externas** de notificación.

[Procedimiento reproducible](../../validation/README.md) · [Reporte completo](repeatability.json).

| Medida | Resultado |
| --- | --- |
| Fecha analítica fija | 2026-09-28 |
| Run inicial | `d5d11418-2ba6-4380-90ae-4ad0a6e9fc1c` |
| Run repetido | `cb39184b-f65d-4603-92c2-37ffdb5d7115` |
| Publicación | Ambos completed; dos runs de auditoría |
| Productos | 159: 115 comerciales + 44 históricos |
| Stock | 206 observaciones aceptadas de 230 leídas |
| Pedidos / líneas | 358 / 1.101; 30 pedidos parciales |
| Incidencias inicial / repetición | 222 / 178; diferencia de 44 creaciones de históricos |
| FKs, claves únicas y contadores | Comprobados sobre las tablas MySQL; sin discrepancias |
| Negocio tras repetir | Igualdad exacta de las cuatro tablas, excluido solo last_run_id |
| SHA-256 del negocio, ambas cargas | `f14438e6e9d777f64826857e1ed314793896ededc2f891171690fbf1b15fe0f1` |
| Fuentes | Hashes idénticos antes/después y entre runs; el reporte incluye los cuatro ficheros y páginas recibidas |
| API original | 5 páginas, 230 filas por carga; la primera necesitó reintentos en páginas 2 y 4 |

Las tablas originales no se han modificado. No se usan fixtures sintéticas para estos resultados. El hash incluye IDs y demuestra igualdad entre estas dos cargas, no entre bases con otro historial.

### Reconciliación y cifras

- Catálogo: **133 = 115 aceptadas + 15 rechazadas + 3 deduplicadas**.
- Stock: **230 = 206 + 24 + 0**.
- Pedidos: **1.142 = 1.101 + 33 + 8**. Hay 359 IDs distintos de origen y 358 pedidos cargados. Falta `PED-2025-00122`, fila 390, auditado con `MISSING_ORDER_DATE`; no es pérdida silenciosa.
- Facturación: **1.381.450,43**, **269** pedidos elegibles, ticket **5.135,50**; 23 de esos pedidos son parciales.
- Margen conocido estimado: **−2.954.287,69**; ventas con coste **1.248.262,11**, sin coste **133.188,32**, cobertura **0,9036**. Se mantienen los avisos de costes contradictorios y moneda/IVA sin confirmar.
- Agosto de 2026: **56.696,84**. Dieciocho meses de serie, septiembre parcial. Bajo mínimos: **12 productos**.

Un recálculo independiente con Decimal sobre líneas MySQL coincidió en facturación, número de pedidos elegibles, margen conocido, importes con/sin coste y cada mes/unidades. Las sumas de canales y categorías coinciden con el total. No sustituye la reconciliación contable: no se dispone de ese origen. El resto de consultas y límites se verifica en la suite y en las evidencias F8–F10.

## Pruebas y navegador

- **397 tests aprobados**, ninguno omitido; 347 sin BD y 50 de integración contra MySQL temporal en `f4_test_delivery`. Incluyen normalización, límites/errores, tarifas, paginación HTTP simulada, FKs, CHECKs, transacciones, rollback, idempotencia, históricos, SQL, web y entrega Make simulada.
- El primer intento se lanzó mientras el ETL real usaba la misma instancia MySQL: 34 tests fueron rechazados por el advisory lock global. Fue un error del orden de validación, no una modificación de reglas; se repitió toda la suite secuencialmente y pasó en 6,99 s. La guía evita esa concurrencia.
- Un aviso conocido: deprecación Starlette/TestClient con httpx. No se silenció ni se añadió otro cliente HTTP.
- Ruff `check` y `format --check`: correctos en `src`, `tests` y `docs/validation` (42 archivos).
- Web del clon en puerto 18080: KPIs y avisos coincidentes; gráfico de barras/línea dibujado; búsqueda `destornillador` + `Herramienta manual` devuelve cuatro productos, incluido PRV-2002 desconocido; limpiar restaura 115 resultados, paginación avanza de 1 a 2. Consola sin errores/avisos observados.
- [Panel completo](dashboard.png) y [gráfico de evolución visible](evolution.png): capturas auténticas del navegador, sin retocar ni reconstruir. No muestran clientes ni credenciales. La revisión responsive completa se conserva en [F10b](../f10b/README.md); F12 no repite una auditoría de diseño.
- La consulta del [guion de demo](../../delivery/demo.md) se ejecutó y devolvió el rechazo de PRV-9001 (localizador 6) y el pedido sin fecha (390).

## Make, Git y revisión de entrega

Make no se ejecuta en F12. Se revisan el JSON del blueprint y la evidencia externa del 27/09/2026: [ambas rutas completadas](../../../make/capturas/f10-real-etl-destinations.png), [fila final](../../../make/capturas/f10-real-sheets-verified.md) y [reenvío del mismo run](../../../make/capturas/f10-real-etl-repeat.png). El escenario original acredita A09; la copia importada y recuperación ante fallo de destino mantienen sus [límites](../../../make/README.md#cierre-y-límites-de-verificación).

La API pública de GitHub confirmó repositorio público, main por defecto y **seis PR merged a main**, con descripción y ramas distintas: etl-products, etl-stock, orders, dashboard, make-integration y ui-ux. Los enlaces están en [SOLUCION](../../../SOLUCION.md#entrega-y-git). No se presenta como creada o integrada una PR de F12 inexistente.

Se comprobaron **168 enlaces locales y anclas, sin referencias rotas**, y `git diff --check` sin incidencias. La revisión de seguridad no encontró coincidencias de los patrones indicados en **274 blobs de texto del historial** ni en el árbol de trabajo. Incluye patrones de webhooks Make, tokens Google/GitHub y claves privadas en los blobs de texto del historial accesible y el árbol de trabajo; revisión del blueprint saneado y las capturas de entrega. Los valores demo de README/Compose son públicos y no se confunden con credenciales reales. No se lee `.env` para esta revisión ni se publica un dump. Este control acotado no equivale a una certificación exhaustiva de ausencia de secretos. `.DS_Store` deja de versionarse conservando sus archivos locales.

## Aceptación final y pendientes

| Criterio | Evidencia / estado |
| --- | --- |
| A01–A05 | Cuatro fuentes, precio, FKs, auditoría e idempotencia: regresión MySQL + dos cargas F12 + trazas F3–F7 |
| A06–A08 | Catálogo, gráfico/KPIs y bajo stock: regresión SQL/web, recálculo y navegador; reglas y limitaciones explícitas |
| A09 | Escenario real F10, dos destinos y fila contrastada; sin atribuir resultados a pruebas no realizadas |
| A10 | Arranque desde clon/venv/BD nuevos ejecutado y documentado, con pasos de carga y migración completos |
| A11 | Código funcional main probado, seis ramas/PR verificadas; **pendiente integrar la documentación F12** para completar la entrega final en main |
| UX01–UX06 | [F10b](../f10b/README.md) integrada mediante PR 6; F12 conserva UI/reglas y comprueba el arranque |
| Correo | [Borrador y adjuntos](../../delivery/email.md) preparados; **no enviado** |

No queda una implementación obligatoria identificada por estos controles. Quedan la revisión/integración de F12 y el envío de entrega. Las decisiones comerciales abiertas, el benchmark de 5 M y los extras F11 son límites o trabajo futuro, no garantías inventadas ni requisitos nuevos para esta prueba.
