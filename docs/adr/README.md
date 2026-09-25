# Registro de decisiones de arquitectura

Un Architecture Decision Record (ADR) conserva el contexto, la decisión, las alternativas y sus consecuencias para que un cambio no dependa de recordar una conversación. Las reglas de cada campo viven en [DATA_RULES.md](../../DATA_RULES.md), no requieren un ADR por caso.

Cada ADR distingue su implementación técnica de los supuestos comerciales pendientes. Una decisión sustituida mantiene su historia y enlaza un ADR nuevo; no renumerar registros antiguos. SOLUCION conserva la evidencia ejecutada y los cambios de versión de reglas.

Crear un ADR solo para una decisión con impacto transversal o alternativas significativas. Usar número secuencial, nombre descriptivo y secciones Estado, Contexto, Decisión, Alternativas consideradas y Consecuencias. Registrar detalles pendientes como tales, sin asumir resultados.

| ADR | Decisión | Estado | Fases |
| --- | --- | --- | --- |
| [001](001-monetary-values-use-decimal.md) | Precisión monetaria Decimal/DECIMAL y redondeo | Implementado; base fiscal pendiente | F1/F3/F8 |
| [002](002-idempotent-etl-loading.md) | Instantáneas, claves únicas y publicación transaccional | Implementado para el dataset de prueba; contrato futuro pendiente | F4–F7 |
| [003](003-historical-orphan-products.md) | Productos históricos mínimos para mantener FKs | Implementado; consulta de margen e interfaz verificadas | F6/F8/F9 |
| [004](004-customer-header-case-insensitive.md) | Cliente equivalente sin distinguir mayúsculas | Aceptado por el usuario e implementado | Corrección F6–F7 |
