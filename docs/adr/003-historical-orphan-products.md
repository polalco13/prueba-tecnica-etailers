# 003 — Productes històrics mínims per conservar les relacions

## Estat

Implementat en F6 i verificat en F7. Després de corregir la capitalització amb l'ADR 004, les càrregues reals v2 conserven 44 històrics: 35 absents del catàleg i 9 rebutjats, relacionats amb 118 línies acceptades i sense FKs òrfenes. Aquestes xifres són històriques de v2: [evidència F12](../evidence/f12/README.md). Amb v3 es recuperen cinc comercials i queden 39 històrics, verificats en [F13](../evidence/f13/README.md). F8 va verificar marge amb cost desconegut separat i cobertura visible; F9 en verifica la presentació, els històrics etiquetats als rànquings i l'exclusió del catàleg comercial.

## Context

El README exigeix FKs reals entre línies i productes i adverteix de SKU que ja no són al catàleg. Rebutjar totes aquestes línies reduiria la cobertura de l'anàlisi de vendes. La font no proporciona nom, categoria ni cost històric recuperables per a aquests SKU.

## Decisió

Crear o reutilitzar un producte identificat per SKU per a cada línia de comanda vàlida sense producte comercial acceptat. Marcar `is_historical=true`, `in_catalog=false`; els camps desconeguts queden a NULL, sense preu ni estoc inventats. L'etiqueta visual d'històric no s'atribueix al proveïdor. Registrar procedència en crear-lo, inclòs si el SKU era absent o si la fila de catàleg va ser rebutjada. Reutilitzar-lo actualitza la referència a l'execució sense repetir HISTORICAL_PRODUCT_CREATED: és un esdeveniment de creació, no un recompte d'històrics presents.

Totes les línies conserven una FK no nul·la. Els històrics contribueixen a vendes i s'agrupen com a sense categoria si falta aquest atribut. El cost desconegut no participa en el marge conegut i la seva facturació queda visible mitjançant cobertura. No es creen productes només perquè l'estoc contingui un SKU desconegut. Si el SKU torna al catàleg, es promociona el mateix ID.

## Alternatives considerades

- Rebutjar línies òrfenes: senzill i vàlid si es declara, però perd històric útil.
- FK nullable: permet guardar la línia, però debilita l'objectiu de relació real i complica estadístiques.
- Un producte genèric per a tots: perd la identitat per SKU i els rànquings.
- Imputar nom, cost o PVP des d'altres productes: inventa informació i distorsiona el marge.

## Conseqüències

Els camps obligatoris per a un producte comercial són nullable per als històrics, amb controls coherents. La interfície i les consultes mostren la distinció i no converteixen NULL a zero. El catàleg comercial exclou històrics per defecte; les anàlisis de comandes els conserven. El marge és una estimació de la part amb cost actual conegut, no una afirmació de rendibilitat històrica completa.
