# 004 — Client de capçalera sense distingir majúscules

## Estat

Acceptat per l'usuari el 24/09/2026: les variants de majúscules i minúscules corresponen al mateix client. Implementat com a correcció de F6–F7; evidència final a [SOLUCION](../../SOLUCION.md#verificación-realizada). No introdueix cap taula ni una identitat global de clients.

## Context

F6 comparava literalment el client després de normalitzar Unicode i espais. F7 va trobar 81 comandes amb diferències només de capitalització: se'n rebutjaven les 324 files amb CONFLICTING_ORDER_HEADER. La regla confonia variants d'escriptura amb una contradicció de capçalera. L'usuari va confirmar expressament que representen el mateix client.

## Decisió

Dins de cada comanda, normalitzar NFC, extrems, espais i sentinelles com abans; comparar el client no buit amb `casefold()`. Conservar com a text de presentació la primera grafia normalitzada vàlida i no buida, en ordre del CSV. No aplicar `title()` ni inventar una capitalització.

Els buits hereten l'etiqueta si hi ha una sola clau equivalent, amb l'avís existent HEADER_VALUE_INHERITED. Si tots són buits, mantenen NULL. Dues claus diferents continuen rebutjant tota la capçalera: no s'eliminen accents, puntuació ni paraules, ni es fa comparació aproximada. Es valida la longitud abans de comparar; un valor invàlid no s'oculta amb una altra variant vàlida.

Versionar el canvi de `catalog-stock-orders-v1` a `catalog-stock-orders-v2`. La signatura `order-line-v1` no canvia: no inclou client. Repetir la validació completa i registrar els nous recomptes, conservant l'evidència anterior com a històrica.

## Alternatives considerades

- Comparació literal: rebutjava variants equivalents confirmades.
- Convertir tot a majúscules en persistir: innecessari per comparar i perd la grafia de presentació.
- Treure accents o usar similitud: podria unir clients diferents i excedeix la confirmació rebuda.

## Conseqüències

Les línies d'aquestes capçaleres es validen individualment; no es prometen 324 línies noves, perquè poden tenir altres errors o duplicats. Es conserva la política de comandes parcials. El resultat és determinista amb el mateix fitxer; reordenar files equivalents pot canviar la grafia mostrada sense canviar la signatura de línia. L'auditoria identifica la versió de regles i continua excloent noms de clients dels extractes i logs.
