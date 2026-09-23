# 001 — Dinero con Decimal y DECIMAL

## Estado

Propuesto. El encargo de planificación exige evitar float para dinero; los detalles de precisión/redondeo son decisiones propuestas.

## Contexto

El README exige precios netos, descuentos y métricas económicas. Las fuentes contienen comas, puntos y símbolos, y combinar descuentos introduce decimales. Una representación binaria aproximada y redondeos distintos entre ETL/web/SQL harían difícil reconciliar resultados.

## Decisión

Parsear texto directamente a `decimal.Decimal`; persistir importes unitarios en `DECIMAL(18,4)` y ratios en `DECIMAL(9,6)`. Calcular coste neto a cuatro decimales y extensión monetaria de cada línea a dos, con `ROUND_HALF_UP`, antes de sumar. Validar desbordamientos y valores no finitos. Serializar dinero como string decimal en JSON; Chart.js solo dibuja cifras ya calculadas y no recalcula KPIs.

Aplicar la gramática de DATA_RULES para no confundir miles con decimales. Mantener la misma política al calcular en MySQL y verificar equivalencia con casos independientes. EUR y base fiscal comparable son supuestos pendientes de confirmación, no conclusiones de este ADR.

## Alternativas consideradas

- Float: simple, pero introduce aproximaciones innecesarias y contradice el encargo.
- Enteros en céntimos: exactos para totales, menos cómodos para precios unitarios con cuatro decimales y porcentajes; requieren otra escala intermedia.
- Redondear solo el total: reduce operaciones, pero difiere de sumar importes de línea redondeados. Se prefiere conciliación por línea explícita.

## Consecuencias

Los tests deben cubrir límites y medios céntimos, y rechazar conversiones vía float. Se documenta el punto de redondeo; cambiarlo puede alterar métricas y exige revisión de reglas/tests. No resuelve por sí mismo IVA ni ausencia de coste histórico.
