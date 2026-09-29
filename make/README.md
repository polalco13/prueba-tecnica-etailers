# Integració amb Make

El [blueprint exportat](escenario.blueprint.json) correspon a l'escenari real, amb webhook, connexions, full i destinatari sanejats. El codi de la crida és a [make_client.py](../src/etl/make_client.py); el resum es persisteix abans de l'enviament, segons l'[ADR 005](../docs/adr/005-persisted-make-delivery.md).

## Disparador i decisions

Després de publicar l'ETL, s'envia `etl-summary-v1`: execució i dates, productes, recomptes per font, motius de rebuig, facturació del mes anterior i productes sota mínims. Els imports són text decimal; moneda i IVA continuen pendents de confirmació. No s'hi inclouen clients ni línies originals. Els exemples [normal](examples/summary.synthetic.json) i [amb alerta](examples/alert.synthetic.json) són sintètics.

El filtre inicial exigeix versió correcta, estat `completed` i `run_id` informat. El processament és seqüencial i registra primer l'històric:

1. **Històric:** busca `run_id` a Sheets i afegeix la fila només si no existeix.
2. **Alerta:** aplica `rows_rejected > rejection_threshold OR low_stock_count > 0`; busca la fila i envia Gmail només si `email_sent_at` és buit. Després actualitza aquesta marca.

Els duplicats i els avisos no disparen una alerta per si sols. Els errors complets de l'ETL queden a l'auditoria local i no generen un resum d'èxit.

## Importació i configuració

1. Importar el blueprint en un escenari nou i desactivat.
2. Crear o seleccionar Custom webhook [1], autoritzar Sheets [3/9/15/17] i Gmail [16]. Assignar el full `ejecuciones` i un destinatari propi; revisar el contingut del correu abans d'executar.
3. Crear les capçaleres A–O en aquest ordre:

```text
run_id | finished_at | status | as_of | products_loaded | rows_rejected |
rows_json | rejected_by_reason_json | previous_month | revenue_previous_month |
low_stock_count | low_stock_products_json | rejection_threshold | alert_required | email_sent_at
```

4. Mantenir **Process data in order**, cerques exactes per ID amb límit 1 i entrada **Raw** en les dues escriptures. JSON [10/13/14] serialitza `rows`, `rejected_by_reason` i `low_stock_products` per separat a G/H/L.

Una cerca sense coincidències emet un bundle buit; l'agregador [7] pot tenir longitud 1. El filtre d'execució nova comprova el número de fila, no la longitud:

```text
{{ifempty(get(7.array; "1.__ROW_NUMBER__"); 0)}}
Numeric operators: Equal to
0
```

El filtre de correu pendent és `15. Row number > 0` AND `15. email_sent_at (O) Does not exist`. Update a Cell [17], després de Gmail, usa la cel·la `O{{15.__ROW_NUMBER__}}` i aquest valor:

```text
{{formatDate(now; "YYYY-MM-DD HH:mm:ss"; "UTC")}} UTC
```

La configuració o la importació no autoritzen per si soles un enviament de correu. Cal una instrucció explícita amb destinatari i contingut revisables abans d'executar una prova externa que enviï missatges.

## Configuració local i reenviament

Aplicar `.venv/bin/python -m src.db migrate` fins a `004_make_delivery`. Les variables arriben de l'entorn privat:

| Variable | Valor inicial | Ús |
| --- | --- | --- |
| `MAKE_WEBHOOK_URL` | buit | HTTPS del webhook; buit desactiva l'enviament. No versionar ni publicar. |
| `MAKE_TIMEOUT` | 10 | Segons per operació de xarxa (1–60). |
| `MAKE_REJECTION_THRESHOLD` | 0 | Llindar absolut (0–1.000.000); l'alerta s'activa quan se supera. |

```bash
.venv/bin/python -m src.etl
.venv/bin/python -m src.etl --resend-make RUN_ID
```

El reenviament usa el resum guardat, sense tornar a carregar les dades. Si ja va ser acceptat, `--force` repeteix el POST després de revisar Make. No hi ha reintents HTTP automàtics: un timeout pot haver tingut efecte remot. El codi de sortida 2 indica negoci publicat amb entrega no confirmada; l'estat i els intents queden a `etl_runs`. Un estat `pending` després d'una caiguda també requereix revisar Make abans de reenviar.

<a id="cierre-y-límites-de-verificación"></a>

## Tancament i límits de verificació

El 27/09/2026 l'ETL real `c1a93f67-6990-4748-8efa-c18bc6777b42` va publicar **115 productes, 72 files rebutjades i 12 productes sota mínims**, amb facturació d'agost **56.696,84**. Aquestes xifres corresponen a la versió d'aquella data. La [captura](capturas/f10-real-etl-destinations.png) mostra l'escenari i les dues rutes completades. L'usuari va aportar el correu rebut i la fila de Sheets: una execució, valors i JSON contrastats i `email_sent_at=2026-09-27 15:34:53 UTC`.

També es van observar el cas sense alerta, el rebuig de contracte i el bloqueig de reenviament. Les captures intermèdies es van retirar de l'entrega i continuen a l'historial Git.

**Límits:** HTTP 2xx confirma recepció, no l'execució dels destinataris. Si Gmail envia i falla l'escriptura de la marca, un reenviament pot duplicar el correu. La recuperació externa i la concurrència no es van provar. La importació es va confirmar, però les connexions i l'execució d'aquesta còpia no estan verificades; l'evidència correspon a l'escenari original. La F14 conserva aquesta evidència i no envia notificacions ni modifica l'escenari extern.

Referències: [blueprints](https://help.make.com/blueprints), [Google Sheets](https://apps.make.com/google-sheets-modules).
