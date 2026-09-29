# Incrementos y estado del proyecto

El [README](README.md) define la entrega. [SOLUCION](SOLUCION.md) contiene arranque/resultados; [DATA_RULES](DATA_RULES.md), las reglas; [TECH_SPEC](TECH_SPEC.md), la arquitectura. Cada fase se solicita por separado. El historial conserva el proceso anterior, sin repetir aquí todas sus tareas, comandos o propuestas.

## Incrementos realizados

| Fases | Resultado | Rama / integración |
| --- | --- | --- |
| F0–F4 | Entorno, normalizadores, catálogo/tarifas y persistencia MySQL. | `feature/etl-products`, PR 1 |
| F5 | API paginada, reintentos y stock consolidado. | `feature/etl-stock`, PR 2 |
| F6–F7 | Pedidos, históricos, cuatro fuentes atómicas e idempotencia. | `feature/orders`, PR 3 |
| F8–F9 | Consultas reconciliadas, catálogo y panel. | `feature/dashboard`, PR 4 |
| F10 | Resumen persistido y destinos reales en Make. | `feature/make-integration`, PR 5, `ff53b1c` |
| F10b | Mejora de lectura/navegación de la web. | `feature/ui-ux`, PR 6, `aab89b9`; [alcance](docs/phases/f10b-ui-ux.md) |
| F12 | Arranque limpio, validación y documentación de entrega. | `feature/delivery-docs`, PR 7, `177ec37`; [evidencia histórica](docs/evidence/f12/README.md) |
| F13 | Corrección de costes/importes y documentación condensada. | `feature/final-review`; [fase](docs/phases/f13-final-review.md), [evidencia](docs/evidence/f13/README.md) |

Las PR 1–7 están integradas en main según el historial local. F13 está implementada y validada en su rama; integración pendiente. El correo de entrega no está acreditado. F11 (incremental, contenedor Python, comparativa anual) no fue elegido.

## Corrección final

Orden ejecutado: fijar reglas/tests → validar catálogo → comprobar ventas/margen y repetibilidad en MySQL aislado → revisar panel → actualizar entrega y reducir documentación.

La calidad de coste se verifica después de calcular el neto según XML y antes de seleccionar ganador. La reparación de un único `?` final se limita al dinero del CSV de catálogo y se audita. La versión pasa a `catalog-stock-orders-v3`; las ventas aceptadas y la firma de línea se conservan. No se introducen extras ni envíos externos.

Aceptación: alternativas de coste válidas en PRV-2013/2061, cinco productos recuperados, descartes trazables, ventas conservadas, cifras recalculadas independientemente, FKs/rollback/repetibilidad y regresiones aprobadas. Documentación propia ≤11.025 palabras frente a 22.050 iniciales, sin perder requisitos. La guía de fase precisa casos límite y el alcance secundario de Make.

## Trabajo Git y cierre

Mantener ramas funcionales `feature/`, commits pequeños por cambio coherente y PR con problema, comportamiento resultante y validación real. No fabricar historial, renumerar PR ni incluir cambios ajenos. Antes de integrar: tests relacionados/regresiones, lint/formato, fuentes intactas, diff y documentación revisados. Main debe contener un incremento funcional.

F13 tiene un commit funcional con reglas/tests y otro documental con evidencia. La PR no implica autorización para enviar correo; preparar contenido y destinatario y obtener instrucción explícita antes del envío. Los límites de Make siguen documentados, sin fingir que una edición local se aplicó en la cuenta.

Terminar al cerrar el alcance solicitado. Cualquier ampliación requiere otra petición. No ejecutar incremental, nuevas integraciones o cambios de negocio por iniciativa propia; cuando cambie una regla, actualizar DATA_RULES, tests y ADR si afecta a una decisión transversal.
