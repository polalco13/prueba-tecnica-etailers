# 005 — Resum persistit i entrega independent a Make

## Estat

Implementat i verificat en F10, integrat a main amb PR 5 (`ff53b1c`). Resum, client i reenviament provats amb MySQL temporal i HTTP simulat; ETL real distribuït a Sheets/Gmail, amb fila, marca i bloqueig de reenviament acreditats. A09 satisfet; blueprint sanejat, captures i guia disponibles. L'usuari va decidir acabar les proves manuals. La recuperació de destinataris i la configuració/execució de la còpia importada no estan verificades; la importació del fitxer es va confirmar textualment. [Límits de tancament](../../make/README.md#cierre-y-límites-de-verificación).

## Context

La càrrega confirmada ha de sobreviure a un error de Make. Un reenviament dies després no ha de barrejar els recomptes de l'execució anterior amb vendes o estoc actuals. Un HTTP 2xx pot confirmar només que Make ha posat el webhook a la cua, i un timeout pot arribar després d'executar un destinatari.

## Decisió

- Guardar `etl-summary-v1` a `etl_runs.make_summary` en la mateixa transacció que completa les quatre fonts. Es calcula abans del commit i sota el bloqueig de l'escriptor; el POST sempre es fa després. Conserva data analítica, zona, recomptes, llindar i imports com a text Decimal, sense clients ni credencials.
- Només les execucions completades tenen resum enviable en v1. Els errors de l'ETL conserven auditoria failed i sortida 1; no s'envien vendes antigues com si fossin de l'intent fallit. Alertar d'errors complets exigiria un altre contracte explícit. La condició de qualitat d'una càrrega completada és `rows_rejected > threshold OR low_stock_count > 0`, amb llindar inicial configurable 0. Duplicats i avisos no sumen als rebuigs.
- Sense URL configurada es guarda el resum i no s'envia. Amb URL es fa un POST per invocació, sense redireccions ni proxies de l'entorn, amb timeout per operació de xarxa de 10 segons per defecte. No es reintenta automàticament una operació amb possibles efectes externs: el CLI permet reenviament explícit amb el mateix run_id i JSON.
- Estats d'entrega: `not_applicable` (no configurada), `pending` (pendent o intent iniciat), `accepted` (HTTP 2xx), `failed` (altre HTTP) i `uncertain` (excepció de xarxa). Intents i dates es confirmen abans i després de l'HTTP. Una caiguda deixa pending amb intents >0; cal revisar Make abans de reenviar. Si falla l'escriptura de la resposta HTTP, la càrrega publicada no es marca failed; el CLI informa sortida 2.
- Un bloqueig MySQL per execució impedeix enviaments locals concurrents. Un resum accepted no es torna a enviar sense `--force`, reservat per recuperar destinataris després de revisar Make. Mai es reconstrueixen resums d'execucions antigues sense JSON guardat.
- A Make, processar webhooks seqüencialment i buscar run_id a Sheets abans d'afegir una fila. El correu necessita una marca separada d'entrega; l'existència de la fila d'històric no demostra que s'hagi enviat. Hi ha una finestra de duplicació si Sheets o el correu completen l'efecte però es perd la resposta. No es promet entrega exactament una vegada.

## Alternatives considerades

- Revertir MySQL si falla Make: invalidaria dades confirmades i no pot desfer un correu.
- Recalcular en reenviar: produiria un resum diferent per al mateix run_id.
- Reintentar POST automàticament davant qualsevol error: pot duplicar efectes externs abans que l'operador revisi l'escenari.
- Construir un blueprint fictici: no acredita mòduls, connexions ni execució real. Es conserva l'exportació real de l'usuari sanejada, amb la configuració corregida acreditada pel segon fitxer, sense inventar canvis aplicats al compte.

## Conseqüències

La migració `004_make_delivery` afegeix metadades sense modificar taules de negoci. Cal aplicar-la explícitament: no actualitza volums per si sola. Un error en generar el resum fa rollback de tota la publicació i conserva l'anterior. Un error HTTP posterior conserva la nova publicació. L'acceptació HTTP s'audita separadament de la verificació de destinataris. F10 acredita l'execució real i es tanca amb els límits externs documentats; no promet recuperació de destinataris provada ni entrega exactament una vegada.
