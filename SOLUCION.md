# Solució

Aquest projecte integra catàleg, tarifes, comandes i estoc en MySQL i ofereix una web de consulta del negoci. Després de cada càrrega completada, Make pot registrar l'execució a Google Sheets i enviar una alerta per Gmail si hi ha incidències o productes sota mínims.

El [README](README.md) conserva l'enunciat original. Les regles detallades són a [DATA_RULES](DATA_RULES.md), les decisions d'arquitectura als [ADR](docs/adr/README.md) i la configuració externa a la [guia de Make](make/README.md).

## Arrencada des de zero

Calen Docker i Python 3.13. Les versions de les dependències estan fixades a [requirements.txt](requirements.txt). L'entorn s'ha verificat amb Python 3.13.13, Compose 2.38.2 i MySQL 8.0.46.

```bash
git clone https://github.com/polalco13/prueba-tecnica-etailers.git
cd prueba-tecnica-etailers
test -f .env || cp .env.example .env
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
docker compose up -d --wait
curl --fail http://localhost:3001/health
.venv/bin/python -m src.db migrate
MAKE_WEBHOOK_URL= .venv/bin/python -m src.etl
.venv/bin/python -m uvicorn src.web.app:app --host 127.0.0.1 --port 8000
```

Obrir el [panell local](http://127.0.0.1:8000). Compose inicia MySQL al port 3307 i l'API d'estoc al 3001. Les credencials demo dels contenidors són literals: editar `.env` configura el procés Python, però no reconfigura aquests serveis. La còpia de `.env.example` només es fa si `.env` no existeix.

El healthcheck de MySQL executa `SELECT 1` per TCP amb l'usuari i la base del contenidor. Això evita donar el servei per preparat només perquè respon un `mysqladmin ping`. A més, `migrate` fa fins a sis intents de connexió davant errors transitoris, amb esperes d'1, 2, 4, 8 i 10 segons. Una contrasenya incorrecta o una base inexistent fallen immediatament. Només es reintenta la connexió inicial; no es repeteixen migracions ni transaccions després d'un error SQL.

Cal aplicar les migracions 001–004 també amb Make desactivat. Repetir `migrate` conserva les migracions aplicades. Els scripts de `db/init` no actualitzen volums existents: no cal esborrar dades per actualitzar l'esquema. La web consulta l'última publicació i no executa l'ETL ni envia notificacions.

Python llegeix `.env` sense sobreescriure les variables reals del procés. A més dels camps de `.env.example`, es poden indicar `ORDERS_CSV_PATH` (per defecte `data/pedidos_historico.csv`), `BUSINESS_TIMEZONE` (Europe/Madrid) i `LOG_LEVEL` (INFO). Els controls operatius de l'API són:

| Variable | Valor inicial | Rang |
| --- | ---: | --- |
| `STOCK_PER_PAGE` | 50 | 1–100 |
| `STOCK_ATTEMPTS` | 5 | 1–10 |
| `STOCK_CONNECT_TIMEOUT` / `STOCK_READ_TIMEOUT` | 5 / 15 segons | 1–120 |
| `STOCK_REQUESTS_PER_MINUTE` | 30 | 1–40 |
| `STOCK_BUDGET_SECONDS` | 300 | 1–3600 |

La paginació verifica avanç i totals constants. Els reintents usen espera exponencial des d'1 segon, variació aleatòria de 0–1 i límit de 30; un 429 respecta Retry-After, sempre dins del pressupost. Els timeouts són per operació de xarxa. No hi ha redireccions ni proxies de l'entorn. Les consultes i els filtres web són parametritzats; una configuració o base no disponible retorna 503 amb un missatge sanejat, i les entrades malformades, 422.

## Arquitectura, esquema i execució

El flux és extracció de les quatre fonts, normalització i validació, publicació transaccional en MySQL i consultes de catàleg i mètriques. El resum de Make es guarda amb el negoci i el POST es fa després del commit.

S'usa PyMySQL per mantenir SQL visible i parametritzat; httpx serveix tant per a estoc com per al webhook. FastAPI, Jinja2 i Uvicorn donen una web HTML senzilla, i Chart.js es distribueix localment per dibuixar el gràfic. La biblioteca estàndard cobreix CSV, XML, Decimal, dates i logging. No s'ha introduït ORM, SPA ni procés npm; cada dependència resol una necessitat concreta i té versió fixada.

| Taula | Finalitat i relacions |
| --- | --- |
| `products` | SKU únic, cost net, PVP, categoria i estoc, amb atributs desconeguts a NULL. |
| `orders` / `order_lines` | Una capçalera per ID d'origen i línies amb FKs a comanda, producte i execució. La signatura de línia és única per comanda. |
| `stock_by_warehouse` | Una observació per producte i magatzem, amb FK al producte i a l'execució. |
| `etl_runs` / `rejections` | Estat de cada execució i incidències amb font, fila, acció, motiu i extracte limitat de l'original. |

Les [migracions](db/migrations/) creen taules InnoDB/utf8mb4 amb FKs, UNIQUE i CHECK. Els diners es calculen amb Decimal des de text i es guarden en DECIMAL. Si una comanda vàlida apunta a un SKU absent o rebutjat al catàleg, es crea un producte històric mínim: conserva vendes i relacions, sense inventar cost, categoria o estoc. Si torna al catàleg, es reutilitza el mateix ID.

Les quatre fonts es validen abans de publicar-les en una transacció. Un error conserva la publicació anterior i un bloqueig MySQL impedeix escriptors simultanis. Repetir la càrrega sincronitza la instantània sense duplicar negoci; l'auditoria creix amb cada execució. Sense ID de línia ERP, dues línies legítimes idèntiques no es poden distingir d'un duplicat.

| Sortida de l'ETL | Significat |
| --- | --- |
| `0` | El negoci s'ha publicat i Make està desactivat o ha acceptat el webhook amb HTTP 2xx. |
| `1` | L'ETL ha fallat i no ha publicat una nova instantània. |
| `2` | El negoci està publicat, però l'entrega a Make no està confirmada. |

Una execució que queda `running` després d'una caiguda necessita revisió. Una notificació es pot recuperar amb `python -m src.etl --resend-make RUN_ID`; si ja consta `accepted`, cal `--force` després de revisar Make per evitar repetir efectes externs.

## Decisions sobre les dades

El catàleg es llegeix en Latin-1 amb `;`, les comandes en UTF-8 amb BOM i coma, i les tarifes XML en UTF-8. Els lectors respecten cometes. Una fila amb columnes incorrectes es rebutja; un fitxer il·legible fa fallar l'execució. Els sentinelles representen NULL, i els diners ambigus es rebutgen. Un EAN invàlid o científic i altres atributs opcionals invàlids es descarten com a camp, sense perdre el producte ni reconstruir dígits. Un pes zero continua sent zero.

**Per què es recupera el `?` final?** El fitxer conté literalment imports com `60,56?`. La posició del caràcter i la resta de l'import suggereixen un símbol monetari degradat, però no es pot confirmar que l'original fos un €. Canviar la descodificació no el recupera. Per això es normalitza un únic `?` final només al cost/PVP del catàleg, si la resta passa la gramàtica, i es registra l'original amb `NORMALIZED_CURRENCY_SUFFIX`. No s'eliminen interrogants interiors ni es relaxen comandes o XML.

El preu net segueix la prioritat de l'enunciat: una excepció XML preval sense altres descomptes; si no existeix, s'aplica `cost × (1−descompte categoria−descompte marca)`. Els descomptes són additius: sobre 100, un 10% i un 5% donen 85, no 85,50.

**Per què es rebutja un cost net superior al PVP?** És una validació conservadora de qualitat del catàleg, sota el supòsit pendent de base fiscal comparable. S'aplica després de tarifes i arrodoniment, abans de resoldre duplicats, i audita `COST_EXCEEDS_PVP`. La igualtat és vàlida. No és una regla universal de rendibilitat ni prohibeix que una venda real tingui pèrdues. PRV-2013 i PRV-2061 es recuperen amb alternatives coherents ja presents a la font, sense imputar costos.

**Per què es conserva la primera fila de PRV-2104?** Té costos 49,84 i 46,15, tots dos plausibles davant el PVP 94,62. Després de validar candidats, es conserva el primer i s'audita el conflicte; el cost net escollit és 45,3544. Les files tenen la mateixa data d'alta, que no és una data d'actualització del preu. L'ordre dona repetibilitat, no certesa comercial: caldria confirmar el preu vigent amb el proveïdor.

Les capçaleres de comanda han de ser coherents. Els buits hereten només un valor inequívoc; el client es compara sense distingir majúscules, sense unir noms semblants. `10%`, `10` i `0,1` són un descompte del 10%; `1` és un 1%. Es rebutgen quantitats zero o fraccionàries, i els negatius només s'admeten en DEVUELTO. Una comanda parcial conserva les línies vàlides; les repetides es dedupliquen per signatura.

L'estoc físic suma magatzems vàlids i conserva les reserves separadament. Absència o invalidesa són NULL, mai zero. L'API es descarrega completa, amb reintents per errors transitoris i 500/429, respectant Retry-After; una extracció incompleta no publica una suma parcial.

## Facturació i marge

La facturació operativa inclou ENVIADO i COMPLETADO amb línies positives acceptades des d'abril de 2025 fins a la data analítica. Pendents i cancel·lades no acrediten venda; les devolucions es conserven però no es resten automàticament perquè no hi ha relació amb la venda original. Les comandes parcials aporten només les línies acceptades.

L'import és quantitat per preu de comanda després del descompte. S'arrodoneix cada línia a cèntims amb ROUND_HALF_UP abans de sumar. El marge conegut resta el cost net actual dels productes venuts, estès i arrodonit també per línia. Les vendes sense cost es mostren separadament, amb cobertura visible; un cost desconegut no es tracta com a gratuït. EUR, base fiscal i ús del cost actual com a estimació històrica són supòsits pendents de confirmació comercial.

El panell mostra evolució mensual i unitats, facturació, comandes, tiquet mitjà, canals, categories, top 10, marge i cobertura. La taula mensual es pot consultar sense JavaScript. Un producte sota mínims és vigent, té estoc físic conegut inferior a 5 i vendes elegibles en els últims tres mesos naturals inclusius. Cerca, categoria i paginació només filtren el catàleg, no els indicadors globals.

## Automatització amb Make

El resum es congela en publicar perquè un reenviament no barregi xifres d'una execució antiga amb dades actuals. Make registra primer el run_id a Sheets, després d'una cerca que evita inserir-lo de nou. Gmail envia alerta si les files rebutjades superen el llindar, inicialment zero, o si hi ha estoc baix; després marca `email_sent_at`. Duplicats i normalitzacions no inflen els rebuigs.

HTTP 2xx acredita recepció del webhook, però no confirma que Sheets o Gmail hagin completat l'operació. La [guia de Make](make/README.md) inclou blueprint, configuració, captura real, reenviament i límits. La F14 manté l'evidència externa anterior i no envia notificacions.

<a id="verificación-realizada"></a>

## Verificació realitzada

El 29/09/2026 s'ha validat el commit funcional F14 `6f03c19` en un clon net i un MySQL temporal sense volums de l'usuari. El primer `migrate` ha funcionat immediatament després de `up --wait`; el segon ha confirmat les quatre migracions ja aplicades.

Amb regles v3, fonts originals i data analítica fixa **28/09/2026**, dues càrregues han deixat el mateix negoci: **120 productes comercials, 39 històrics, 358 comandes i 1.101 línies**. Facturació **1.381.450,43**, 269 comandes elegibles, tiquet mitjà **5.135,50**, marge conegut **575.355,92**, cobertura **95,51 %** i 12 productes sota mínims. Fonts, imports, contribucions dels SKU revisats i tots els mesos coincideixen amb F13; el recàlcul Decimal independent coincideix amb SQL. Les FKs i els recomptes s'han comprovat a MySQL, amb Make desactivat.

La suite completa ha aprovat **467 tests: 416 unitaris i 51 MySQL, sense omissions**. Inclou 24 casos nous d'arrencada, sense esperes reals ni serveis en els tests unitaris. Ruff i format són correctes, i els enllaços i les àncores locals s'han comprovat. Es conserva l'avís conegut de deprecació Starlette/TestClient. El procediment i el registre F14 són a la [guia de validació](docs/validation/README.md); els [informes F13](docs/evidence/f13/README.md) i les [captures](docs/evidence/README.md) conserven la seva data i abast originals.

Com a mostra del càlcul, PRV-2013 té cost net `318.52 × 0.82 = 261.1864`. La línia de comanda 345 ven `2 × 509.79 = 1019.58`, amb cost estès 522.37 i marge 497.21. Les incidències es poden consultar per execució, font i SKU sense imprimir clients.

### Execució dels tests

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests docs/validation
.venv/bin/ruff format --check src tests docs/validation
```

Sense la configuració MySQL de proves, els tests de base de dades s'ometen. La guia aïllada prepara bases separades: no usar `catalogo` ni executar pytest alhora que l'ETL en el mateix servidor, perquè comparteixen un bloqueig d'escriptor.

## Escala i límits de l'entrega

Amb cinc milions de línies, el primer límit previsible és memòria. Substituiria la materialització completa per lectura en streaming, staging i lots, amb índexs per capçaleres i signatures, i publicaria després de validar el conjunt. Mesuraria memòria, files per segon, bloquejos i plans SQL abans de precalcular agregats. No s'ha fet aquest benchmark ni es promet un SLA; l'incremental exigeix un contracte de canvis i baixes i un ID estable de línia ERP.

Han quedat fora la càrrega incremental, el contenidor Python i la comparativa anual, tots opcionals. La web és de consulta local, sense autenticació multiusuari ni edició de dades. Codex ha ajudat a implementar i verificar; l'autor ha confirmat les decisions i configurat els destinataris externs. Les proves HTTP simulades no es presenten com a Make real. Les fonts i les dates reals de Git es conserven.
