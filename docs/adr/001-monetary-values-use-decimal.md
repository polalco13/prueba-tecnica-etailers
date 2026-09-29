# 001 — Diners amb Decimal i DECIMAL

## Estat

Implementat per a normalització i persistència en F1–F7 i per a mètriques SQL en F8. Les proves MySQL verifiquen l'arrodoniment d'imports i costos per línia, inclòs mig cèntim. EUR, IVA i comparabilitat comercial continuen pendents de confirmació.

## Context

El README exigeix preus nets, descomptes i mètriques econòmiques. Les fonts contenen comes, punts i símbols, i combinar descomptes introdueix decimals. Una representació binària aproximada i arrodoniments diferents entre ETL, web i SQL dificultarien la reconciliació.

## Decisió

Llegir el text directament amb `decimal.Decimal`; persistir imports unitaris en `DECIMAL(18,4)` i ràtios en `DECIMAL(9,6)`. Calcular el cost net a quatre decimals i l'import estès de cada línia a dos, amb `ROUND_HALF_UP`, abans de sumar. Validar desbordaments i valors no finits. Serialitzar diners com a text decimal en JSON; Chart.js dibuixa xifres ja calculades i no recalcula els indicadors.

Aplicar la gramàtica de DATA_RULES per no confondre milers amb decimals. Mantenir la mateixa política a MySQL i verificar-ne l'equivalència amb casos independents. EUR i base fiscal comparable són supòsits pendents de confirmació, no conclusions d'aquest ADR.

## Alternatives considerades

- Float: simple, però introdueix aproximacions innecessàries i contradiu els criteris de precisió del projecte.
- Enters en cèntims: exactes per als totals, menys còmodes per a preus unitaris amb quatre decimals i percentatges; necessiten una altra escala intermèdia.
- Arrodonir només el total: redueix operacions, però difereix de sumar imports de línia arrodonits. Es prefereix una conciliació explícita per línia.

## Conseqüències

Els tests cobreixen límits i mitjos cèntims i rebutgen conversions via float. Canviar el punt d'arrodoniment pot alterar les mètriques i exigeix revisar regles i tests. La decisió no resol per si sola l'IVA ni l'absència de cost històric.
