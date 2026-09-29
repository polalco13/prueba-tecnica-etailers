# Registre de decisions d'arquitectura

Un Architecture Decision Record (ADR) conserva el context, la decisió, les alternatives i les conseqüències perquè un canvi no depengui de recordar una conversa. Les regles de cada camp són a [DATA_RULES.md](../../DATA_RULES.md) i no necessiten un ADR per cas.

Cada ADR distingeix la implementació tècnica dels supòsits comercials pendents. Una decisió substituïda conserva la història i enllaça un ADR nou; els registres antics no es renumeren. SOLUCION recull l'evidència executada i les versions de regles.

Només es crea un ADR per a una decisió amb impacte transversal o alternatives significatives. S'usa número seqüencial, nom descriptiu i les seccions Estat, Context, Decisió, Alternatives considerades i Conseqüències. Els detalls pendents es registren com a tals, sense donar per fets els resultats.

| ADR | Decisió | Estat | Fases |
| --- | --- | --- | --- |
| [001](001-monetary-values-use-decimal.md) | Precisió monetària Decimal/DECIMAL i arrodoniment | Implementada; base fiscal pendent | F1/F3/F8 |
| [002](002-idempotent-etl-loading.md) | Instantànies, claus úniques i publicació transaccional | Implementada per al conjunt de prova; contracte futur pendent | F4–F7 |
| [003](003-historical-orphan-products.md) | Productes històrics mínims per mantenir FKs | Implementada; marge i interfície verificats | F6/F8/F9 |
| [004](004-customer-header-case-insensitive.md) | Client equivalent sense distingir majúscules | Acceptada per l'usuari i implementada | Correcció F6–F7 |
| [005](005-persisted-make-delivery.md) | Resum persistit i entrega independent a Make | Implementada; destinataris reals acreditats, límits externs documentats | F10 |
