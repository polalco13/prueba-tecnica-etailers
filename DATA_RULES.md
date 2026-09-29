# Regles de dades aplicades

Versió actual: **`catalog-stock-orders-v3`**. El [README](README.md) exigeix decidir i documentar el tractament de les dades brutes. Aquestes són les regles del projecte; els supòsits comercials pendents es recullen al final. El flux, l'esquema i els resultats s'expliquen a [SOLUCION](SOLUCION.md).

## Accions i procedència

Normalitzar conserva el significat; rebutjar una fila exclou l'entitat; descartar un camp conserva l'entitat amb NULL; deduplicar conserva una ocurrència; avisar conserva la dada; fallar una execució impedeix publicar-la. Cada descart o correcció registra execució, font, fila o localitzador, entitat, motiu i camp, acció i un extracte original limitat. No es guarden secrets ni s'imprimeixen clients o payloads sensibles. Una dada desconeguda és NULL, mai zero.

## Catàleg i tarifes

El catàleg es llegeix en Latin-1, amb separador `;`, lector CSV i 11 columnes: SKU, EAN, nom, marca, categoria, cost, PVP, IVA, pes, data d'alta i descripció. Es respecten les cometes i els camps multilínia. Una capçalera o un fitxer il·legible fan fallar l'execució; un nombre incorrecte de columnes rebutja la fila. No es desplacen camps ni es modifica `data/`.

| Cas | Regla |
| --- | --- |
| Valors buits | Després d'eliminar espais als extrems i aplicar casefold, només els tokens complets `N/D`, `NULL`, `-`, `n/a` o buit són absència. SKU, nom, marca, categoria i PVP són obligatoris; els atributs opcionals admeten NULL. |
| Text i identificadors | NFC, normalització d'espais i extrems. Marca i categoria es comparen sense distingir majúscules, conservant accents. SKU i ID es passen a majúscules, sense treure guions ni afegir zeros; màxim 64 caràcters i sense controls. No es trunquen. |
| Diners | Decimal des de text; coma o punt decimal, € o EUR i milers inequívocs. `1.234,56` → 1234.56; `1.234` aïllat és ambigu. Es rebutgen exponents, valors no finits, zero, negatius i desbordaments de DECIMAL(18,4). |
| Sufix monetari degradat | Només en cost/PVP d'aquest CSV: s'admet un únic `?` final si la resta compleix la gramàtica monetària. `60,56?` → 60.56, amb `NORMALIZED_CURRENCY_SUFFIX`, acció normalize/info i original conservat. Es rebutgen `?60,56`, `60?56`, `60,56??` i `?`; `1.234?` continua sent ambigu. No es relaxen altres parsers. |
| EAN | Es netegen espais, cometes exteriors o l'apòstrof inicial d'Excel, i es valida EAN-8/13 i checksum. Buit → NULL; invàlid o científic → camp descartat amb motiu. No es reconstrueixen dígits ni zeros perduts. |
| IVA, pes i alta | Són opcionals: si són invàlids, queden a NULL amb incidència. IVA es tracta com a ràtio; el pes és decimal sense milers, amb zero vàlid i negatius invàlids. La data d'alta és estricta, sense dates inventades. |
| Cost CSV invàlid | El candidat només es pot recuperar amb una excepció XML vàlida que proporcioni el preu net. Amb excepció, s'audita el descart del cost original; sense excepció, es rebutja la fila. |
| XML | UTF-8, seccions Descuentos/Excepciones identificables, sense DOCTYPE. Un fitxer il·legible, una regla general invàlida o tarifes contradictòries per a la mateixa clau fan fallar l'execució. Una regla repetida idèntica es deduplica. |
| Prioritat | L'excepció per SKU preval, sense descomptes addicionals. Si no existeix: `cost × (1 − descompte categoria − descompte marca)`. Un descompte absent és zero; suma ≥1 o net arrodonit ≤0 rebutgen el producte. Una excepció invàlida o un flag addicional diferent de false rebutgen el producte, sense alternativa. |
| Qualitat del cost | Després de calcular i arrodonir el net, es rebutja el candidat amb `net_cost > pvp`: `COST_EXCEEDS_PVP`, conservant net, PVP, origen i fila. La igualtat és vàlida. També es valida l'excepció XML; no se'n tria una altra per ocultar el problema. Això no prohibeix una venda real per sota del cost. |
| SKU duplicat | Es valida cada candidat abans de triar. Entre els vàlids, es conserva el primer del fitxer i s'auditen els altres. Les 11 cel·les idèntiques generen EXACT_DUPLICATE; les diferents, CONFLICTING_PRODUCT_SKU, amb referència a la fila conservada. L'ordre és determinista, però no acredita vigència comercial. |

Els descomptes són additius per decisió de l'exercici: cost 100, 10% i 5% → 85; si fossin seqüencials donarien 85.5. No s'aplica PorVolumen sense compres conegudes, ni ports ni termini de pagament; els termes reconeguts generen un avís. Una excepció sense candidat al catàleg genera UNKNOWN_PRODUCT_SKU, sense crear un producte.

El `?` ja existeix literalment al fitxer. La seva posició final en imports que altrament són vàlids suggereix un símbol monetari degradat, però no confirma que originalment fos un €. Canviar la descodificació no recupera aquest original. La recuperació és una decisió local, limitada i auditada, pendent de confirmar amb el proveïdor.

La comparació entre cost net i PVP és una validació conservadora sota el supòsit de base fiscal comparable, no una regla universal de rendibilitat. A `PRV-2104` hi ha costos 49,84 i 46,15 amb PVP 94,62: tots dos passen la validació. Es conserva el primer, 49,84, que dona net 45,3544. Les dues files tenen la mateixa data d'alta, que tampoc acredita una actualització del preu; caldria confirmar-ne la vigència amb el proveïdor.

## Comandes

UTF-8 amb BOM, separador coma, 9 columnes i lector amb cometes: ID, data, client, canal, estat, SKU, quantitat, preu i descompte. S'agrupa per ID normalitzat. Les dates accepten ISO, dd/mm/yyyy, dd-mm-yyyy, yyyy/mm/dd i hora si n'hi ha; s'agrupen per dia. Una data amb hora i una sense hora del mateix dia són compatibles.

A la capçalera, els buits només hereten un valor inequívoc del grup, amb HEADER_VALUE_INHERITED. El client pot quedar a NULL; es compara amb NFC, espais i casefold i es conserva la primera grafia vàlida no buida. Les variants de majúscules es van confirmar amb l'usuari; no s'uneixen accents, puntuació o noms semblants. Un valor no buit invàlid no s'oculta amb herència. Un conflicte real o una data sense dia recuperable rebutgen la comanda i les seves línies. Una línia invàlida no elimina les altres: la comanda queda parcial si té línies vàlides, i no es carrega si no en té cap. Un fitxer buit, il·legible o sense comandes vàlides impedeix publicar.

Estats canònics: ENVIADO, COMPLETADO, PENDIENTE, CANCELADO i DEVUELTO. Canals: B2B, B2C i marketplace, sense distingir majúscules. Un valor desconegut rebutja la capçalera, sense correspondències aproximades. La quantitat és un enter exacte diferent de zero: `2,0`/`2.0` → 2; es rebutgen fraccions i desbordaments. Només DEVUELTO admet negatius, conservant el signe. El preu unitari positiu és obligatori.

Descomptes: `10%`, `10` i `0,1` → 0.10. Amb `%`, es divideix per 100; sense, [0,1) és ràtio i [1,100] són punts percentuals (`1` → 1%). La ràtio final és [0,1], amb fins a sis decimals; un buit es converteix en zero amb avís. No es reparen sufixos monetaris del catàleg en comandes, XML, quantitats, descomptes o EAN.

La signatura `order-line-v1` és SHA-256 de comanda/SKU/quantitat/preu/descompte canònics, sense fila física. Les signatures repetides es dedupliquen i s'auditen; dues línies legítimes idèntiques són indistingibles sense ID del sistema ERP. La correcció de client va produir v2 i les regles de catàleg, v3, sense canviar signatura ni estats elegibles.

Un SKU vàlid d'una comanda sense catàleg acceptat crea o reutilitza un històric mínim: comercial false, històric true i cost/PVP/estoc NULL. Es conserven vendes i FKs. HISTORICAL_PRODUCT_CREATED es registra només en crear-lo, distingint SKU absent i catàleg rebutjat. Si torna al catàleg, es promociona el mateix ID. Ni l'estoc ni les línies rebutjades creen històrics. [ADR 002/003](docs/adr/README.md).

## Estoc

S'extreu tota l'API, amb totes les pàgines i reintents acotats. Una extracció incompleta genera STOCK_FETCH_FAILED i no publica cap canvi. Un SKU present només a l'API no crea un producte; l'observació es rebutja amb UNKNOWN_PRODUCT_SKU.

Quantitat i reserva són enters exactes entre zero i el màxim BIGINT amb signe, sense booleans, absències ni fraccions. La data ha de tenir zona i ser convertible a UTC/DATETIME; si és invàlida, es rebutja l'observació. `reserved > quantity` genera avís i conserva els dos valors; no es resta la reserva per calcular estoc físic.

Per clau SKU/magatzem, les repeticions normalitzades iguals generen EXACT_DUPLICATE i les versions antigues, SUPERSEDED_STOCK; es dedupliquen totes dues. Es tria l'actualització més recent. Valors contradictoris al mateix instant rebutgen les observacions i invaliden el total del SKU, encara que hi hagi una versió posterior; no es recupera arbitràriament una versió antiga.

Es conserven els magatzems vàlids encara que algun falli; total/data NULL i estat invalid eviten una suma parcial. Sense observacions, l'estat és unknown i el total, NULL. Només un conjunt complet vàlid queda known i suma quantity, inclòs zero real. Una suma desbordada genera NUMERIC_OUT_OF_RANGE i total invàlid. `stock_as_of` és la data màxima acceptada, no una garantia de frescor comuna.

## Mètriques, càrrega i recomptes

La facturació operativa inclou ENVIADO/COMPLETADO i línies positives acceptades des de l'01/04/2025 fins a `as_of`, inclòs. Se n'exclouen pendents, cancel·lades i retornades. Es conserven devolucions sense compensar-les automàticament perquè falta la relació amb la venda original. Les comandes parcials aporten només les línies acceptades.

El net unitari es calcula a quatre decimals; l'import i el cost estès de cada línia, a dos amb ROUND_HALF_UP abans de sumar. Import = quantitat × preu de comanda × (1−descompte). Marge conegut = import − quantitat × net actual arrodonit. Un cost NULL no és gratuït: les vendes sense cost s'informen separadament i cobertura = vendes amb cost / total, NULL si el total és zero. Es conserva un marge negatiu legítim. Tiquet mitjà = vendes/comandes elegibles diferents, NULL si no hi ha comandes.

Canals i categories reconcilien amb el total; els històrics sense categoria tenen un grup explícit. El top 10 s'ordena per facturació descendent i SKU ascendent en empats. Es completen tots els mesos des d'abril de 2025 amb zero real; el mes actual és parcial. Estoc baix: producte vigent, físic conegut <5 i venda elegible en una finestra inclusiva de tres mesos naturals, ajustant el dia a l'últim vàlid. Make usa el mes anterior complet i la mateixa consulta d'estoc baix.

Es publiquen instantànies completes atòmicament, amb reconciliació i un sol escriptor; sense TRUNCATE ni FKs desactivades. Una font que canvia durant la lectura, una instantània buida o un error MySQL/inesperat impedeixen publicar, amb motiu sanejat. Les mateixes entrades i regles conserven el negoci; auditoria i timestamps creixen.

Per font completada: `llegides = acceptades + rebutjades + deduplicades`. Una fila rebutjada compta una vegada encara que tingui diversos motius; els motius poden sumar més que les files. Avisos, camps descartats i normalitzacions no inflen els rebuigs. El resum Make només es genera per completed i es persisteix amb la publicació: alerta si les files rebutjades superen el llindar o hi ha estoc baix. Els errors complets queden failed a l'auditoria local; no s'envien vendes antigues com un èxit fictici.

Supòsits pendents de confirmació comercial: EUR i base fiscal comparable, cost actual com a estimació històrica, descomptes additius, estoc físic sense restar reserves, Europe/Madrid i autoritat de futures exportacions/identitat de línia ERP. No són resultats de proves tècniques.
