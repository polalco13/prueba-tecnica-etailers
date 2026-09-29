# 002 — Càrrega idempotent per instantànies completes

## Estat

Implementada en F4–F6 i verificada en F7 contra MySQL 8: repetició de quatre fonts, rollback i exclusió d'escriptors concurrents. Evidència final a [SOLUCION](../../SOLUCION.md#verificación-realizada). L'usuari va aclarir que el CSV és el fitxer rebut per a la prova: es processa complet com a conjunt de l'exercici, sense atribuir-li un contracte confirmat sobre futures exportacions del sistema ERP. L'entrega a Make correspon a F10.

## Context

El README exigeix repetir l'ETL sense duplicar productes ni comandes. Hi ha duplicats d'origen i les línies no tenen ID estable. Un INSERT simple duplica dades; un upsert per hash sense reconciliació acumularia versions antigues quan una línia canviés. L'API pot fallar després d'algunes pàgines.

## Decisió

Usar claus naturals úniques per a SKU i comanda, i una signatura canònica versionada SHA-256 de comanda/SKU/quantitat/preu/descompte per a línies. Deduplicar signatures iguals amb traçabilitat, declarant que no es distingeixen dues línies legítimes idèntiques. Publicar instantànies completes: upserts d'entitats, eliminació explícita de línies i comandes que ja no pertanyen al conjunt acceptat i actualització d'estoc per magatzem. Els productes absents passen a històrics, no s'esborren.

Extreure i validar abans d'una transacció MySQL de negoci; una instantània il·legible, una extracció incompleta o un fitxer inesperadament buit impedeixen publicar. Les quatre fonts es publiquen atòmicament, amb una sola execució concurrent. Els rebuigs i les execucions fallides s'auditen separadament; les execucions completades es confirmen amb el negoci. Make s'envia després del commit, amb un run_id reutilitzable per reintentar l'entrega.

Amb entrades i regles idèntiques, el contingut de negoci és idèntic. Auditoria, timestamps i notificacions per execució poden augmentar. La comparació usa valors i claus de negoci i exclou metadades de l'execució.

## Alternatives considerades

- INSERT sense comprovacions: incompleix la idempotència.
- Hash per línia sense esborrar signatures antigues: no gestiona correccions.
- Número físic de fila com a identitat: canvia en reordenar o inserir files al CSV.
- Conservar multiplicitat amb índex d'ocurrència: preserva línies legítimes iguals, però també duplicats accidentals; alternativa si el proveïdor confirma aquesta semàntica.
- ID de línia del sistema ERP: preferible quan existeixi, però no és a la font actual.
- TRUNCATE i recàrrega: dificulta FKs i publicació atòmica; no s'usa ni s'esborra el volum per reiniciar.
- Incremental des del principi: exigeix marca de progrés, baixes i regles de reconciliació innecessàries per al primer objectiu; es va reservar a l'opcional F11.

## Conseqüències

Es manté la deduplicació per a aquest exercici: el README adverteix de files repetides i, després de corregir la capitalització del client a l'ADR 004, les vuit línies deduplicades del CSV real coincideixen en les nou columnes originals. Es conserva una ocurrència i se'n registren motiu, fila descartada i fila conservada. Això dona suport al criteri, però no demostra que un ERP real mai emeti dues línies legítimes idèntiques. Abans d'acceptar futures exportacions caldria confirmar-ne la semàntica o demanar un ID estable de línia. Sense aquesta informació no s'afegeixen multiplicitat ni càrrega incremental.

Cal reconciliar el conjunt acceptat, no només escriure registres. Una fila que deixa de ser vàlida no conserva silenciosament el valor anterior en la versió actual. Els tests cobreixen repetició, correcció, desaparició, fallada i concurrència. La política de deduplicació i l'autoritat de la instantània són supòsits de negoci que s'han de confirmar i mantenir visibles. Per a cinc milions de línies es preferirien staging i lots sense canviar el contracte extern de publicació.
