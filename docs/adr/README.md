# Registro de decisiones de arquitectura

Un Architecture Decision Record (ADR) conserva el contexto, la decisión, las alternativas y sus consecuencias para que un cambio no dependa de recordar una conversación. Las reglas de cada campo viven en [DATA_RULES.md](../../DATA_RULES.md), no requieren un ADR por caso.

Los ADR de esta planificación están **Propuestos**: son opciones justificadas por el repositorio, no decisiones implementadas o aprobadas comercialmente. Al implementar, revisar con el responsable, pasar a **Aceptado** cuando corresponda e incluir evidencia/enlace a PR. Una decisión sustituida mantiene su historia y enlaza un ADR nuevo; no renumerar registros antiguos.

Crear un ADR solo para una decisión con impacto transversal o alternativas significativas. Usar número secuencial, nombre descriptivo y secciones Estado, Contexto, Decisión, Alternativas consideradas y Consecuencias. Registrar detalles pendientes como tales, sin asumir resultados.

| ADR | Decisión | Estado | Fases |
| --- | --- | --- | --- |
| [001](001-monetary-values-use-decimal.md) | Precisión monetaria Decimal/DECIMAL y redondeo | Propuesto | F1/F3/F8 |
| [002](002-idempotent-etl-loading.md) | Instantáneas, claves únicas y publicación transaccional | Propuesto | F4–F7 |
| [003](003-historical-orphan-products.md) | Productos históricos mínimos para mantener FKs | Propuesto | F6/F8 |
