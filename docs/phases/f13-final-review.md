# F13 — Corrección final de datos y entrega

Solicitada el 29/09/2026 a partir del veredicto; **implementada y validada en `feature/final-review`**, integración pendiente. [Resultados y límites](../evidence/f13/README.md). El [README](../../README.md) conserva los requisitos; [DATA_RULES](../../DATA_RULES.md) describe reglas v3. El plan previo completo puede consultarse en Git.

## Problema y decisiones autorizadas

La primera fila positiva de PRV-2013/2061 conservaba costes 34.400,16/2.532,60 frente a PVP 539/48,66, pese a alternativas 318,52/23,45. Cinco importes terminaban en `?` y quedaban rechazados. SOLUCION anunciaba F12 pendiente aunque la PR 7 ya estaba integrada.

Se valida **coste neto ≤PVP**, después de XML/redondeo y antes de elegir candidato. Incidencia COST_EXCEEDS_PVP con fuente/fila/SKU/neto/PVP/origen. La excepción XML mantiene prioridad; si resulta incoherente, rechazar sin fallback. Igualdad permitida. Entre válidos, primero del fichero y conflictos auditados: PRV-2104 conserva alternativas plausibles sin fingir una fecha de actualización.

Es un control conservador del catálogo bajo el supuesto de base fiscal comparable. El margen sigue usando ventas reales, admite pérdidas legítimas y muestra coste desconocido. Si todo candidato falla, conservar pedidos mediante histórico con NULL; nunca eliminar ventas para mejorar la cifra ni fijar los 516 k€ del veredicto como objetivo.

Solo coste/PVP del CSV de catálogo admite **un único `?` final** cuando el resto es dinero válido: normalización auditada con original. `?60,56`, `60?56`, `60,56??`, `?` siguen rechazados; `1.234?` sigue ambiguo. No extender la reparación a pedidos/XML/EAN, cambiar encoding ni modificar las fuentes.

## Ejecución y aceptación

| Paso | Archivos / comprobación |
| --- | --- |
| Reglas, auditoría y versión | Catálogo/precios/records/reporting; tests unitarios y DATA_RULES. Reglas v3, firma de línea y resumen Make v1 conservados. |
| Persistencia y métricas | Tests MySQL de FKs/UNIQUE, selección, histórico/promoción, repetición y rollback. SQL de métricas sin cambios. |
| Revisión de cifras | Dos ETL reales con `as_of=2026-09-28`; hashes congelados, recálculo Decimal independiente y muestra manual desde fuentes. Comparación por SKU y agregado, ventas/serie sin cambios. |
| Panel y entrega | Aviso de coste actualizado, margen/cobertura/gráfico, búsqueda/categoría/limpiar/paginación y captura auténtica. |
| Documentación | Estados actuales corregidos, arranque y decisiones legibles, evidencia histórica diferenciada, instrucciones útiles preservadas. |

Casos comprobados: neto superior/igual/inferior al PVP, bruto alto rescatado por descuento/excepción, candidato inválido antes/después de uno válido, todos incoherentes, dos plausibles, duplicado exacto y excepción incoherente sin fallback. Sufijo con coma/punto/espacios, cinco formas observadas, ambigüedad, signos, exponentes y rango; parsers compartidos estrictos. Fixtures sintéticas identificadas, expectativas independientes. Se conserva la regresión de pérdida legítima.

Objetivo documental: de **22.050 a ≤11.025 palabras**. Enumerar `git ls-files '*.md'`, excluir README.md y src/web/static/vendor/, sumar `len(text.split())`. Contar documentos nuevos, incluido este; mover contenido a un archivo histórico no cuenta como reducción. SOLUCION orientativamente ≤1.000 palabras. Mantener requisitos, seguridad, ADR, procedimientos y límites; narraciones antiguas en Git.

## Límites y cierre

Sin dependencias nuevas, extras F11, cambios en facturación/cantidades negativas, fuentes o BD del usuario. Validación aislada con Make desactivado; HTTP simulado para regresiones. Un ensayo externo con correo requiere instrucción explícita, destinatario y contenido revisables.

Revisión secundaria de Make: JSON 10/13/14 serializa tres campos distintos. No se modificó un escenario real sin verificar equivalencia; nombre genérico y posible consolidación quedan identificados como límite secundario. La evidencia del escenario original conserva su fecha; editar localmente una exportación no prueba aplicación en cuenta.

Commit funcional de reglas/tests y commit documental/evidencia; PR breve de esta rama a main sin fabricar historial. Cierre técnico: costes corregidos, cinco productos recuperados, ventas conservadas, cifras explicables, pruebas aprobadas y reducción documental cumplida. Integración y envío se informan por separado.
