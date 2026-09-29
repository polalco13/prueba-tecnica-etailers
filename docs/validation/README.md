# Validació aïllada d'ETL i MySQL

Les eines són al repositori des de PR 7. La [validació v2](../evidence/f12/README.md) va partir d'un clon net el 28/09/2026; la [correcció v3](../evidence/f13/README.md) va comparar dues bases noves el 29/09/2026. La comprovació F14, registrada al final, valida l'arrencada i conserva les xifres v3. El procediment executa el codi de la revisió triada sobre fonts originals; per validar una PR, seleccionar-ne la branca abans d'iniciar els serveis.

Aquesta comprovació d'entrega no afegeix arquitectura productiva. No s'usa la base de l'usuari per a pytest. El Compose auxiliar reutilitza les imatges i el mock originals, canvia noms i ports i usa tmpfs per a MySQL: no munta `mysql_data`. Cal Compose >= 2.24.4 per `!override`; verificat amb 2.38.2. Les contrasenyes següents són exclusivament demo del servei temporal.

## Instal·lació i serveis

```bash
git clone https://github.com/polalco13/prueba-tecnica-etailers.git nortesur-validacio
cd nortesur-validacio
test -f .env || cp .env.example .env
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
docker compose -p nortesur-f12 -f docs/validation/compose.yml up -d --wait
curl --fail http://127.0.0.1:13311/health
```

No iniciar aquest Compose si ja hi ha una validació que usa aquests noms o ports. MySQL queda a 13317 i l'estoc a 13311; el mock conserva els errors 500 aleatoris i el límit de peticions. No copiar els seus logs d'arrencada: contenen el token demo. El healthcheck heretat de MySQL comprova una consulta SQL per TCP amb l'usuari i la base configurats, abans que `up --wait` retorni.

A la terminal del clon nou:

```bash
export DB_HOST=127.0.0.1 DB_PORT=13317 DB_NAME=f12_real
export DB_USER=etailers DB_PASSWORD=etailers
export STOCK_API_URL=http://127.0.0.1:13311/api/v1/stock
export STOCK_API_TOKEN=etailers-demo-token
export MAKE_WEBHOOK_URL=
.venv/bin/python -m src.db migrate
.venv/bin/python -m src.db migrate
.venv/bin/python docs/validation/verify_repeatability.py > /tmp/nortesur-repeatability.json
```

No cal una espera manual abans del primer `migrate`. La connexió inicial reintenta només errors transitoris, fins a sis intents amb esperes d'1, 2, 4, 8 i 10 segons. Un error SQL posterior no torna a executar la migració. El segon `migrate` ha d'indicar que les quatre migracions ja estan aplicades.

El script admet `f12_real` o `f13_real` i exigeix la base triada inicialment buida i Make desactivat. Executa l'ETL real dues vegades, fixa `as_of=2026-09-28`, comprova FKs i recomptes, igualtat del negoci i hashes d'origen, i recalcula imports amb Decimal independentment del SQL analític. Publica un JSON sense clients ni configuració privada; no és una fixture sintètica. No tornar-lo a executar sobre la mateixa base carregada. Per comparar una segona versió com a F13, crear una altra base al contenidor temporal, sense esborrar l'anterior:

```bash
docker exec -i nortesur-f12-mysql mysql -uroot -prootpass <<'SQL'
CREATE DATABASE f13_real CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
GRANT ALL PRIVILEGES ON f13_real.* TO 'etailers'@'%';
SQL
export DB_NAME=f13_real
.venv/bin/python -m src.db migrate
.venv/bin/python docs/validation/verify_repeatability.py > /tmp/nortesur-f13-repeatability.json
```

L'informe inclou commit, hashes, execucions, mètriques i contribució dels SKU revisats; no conté clients. Si es canvia la revisió del codi, fer-ho entre les dues bases, conservant data i fonts.

## Suite completa, de forma seqüencial

Crear una altra base buida **al contenidor temporal**. Els tests administren taules i dades sintètiques; no executar-los contra `f12_real` ni `catalogo`:

```bash
docker exec -i nortesur-f12-mysql mysql -uroot -prootpass <<'SQL'
CREATE DATABASE f4_test_delivery CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'f4_tester'@'%' IDENTIFIED BY 'f12-test-only';
GRANT ALL PRIVILEGES ON f4_test_delivery.* TO 'f4_tester'@'%';
SQL
F4_TEST_DB_HOST=127.0.0.1 F4_TEST_DB_PORT=13317 \
F4_TEST_DB_NAME=f4_test_delivery F4_TEST_DB_USER=f4_tester \
F4_TEST_DB_PASSWORD=f12-test-only .venv/bin/python -m pytest -q
.venv/bin/ruff check src tests docs/validation
.venv/bin/ruff format --check src tests docs/validation
```

**No executar pytest mentre l'ETL s'està executant en aquesta instància MySQL**, encara que les bases tinguin noms diferents: el bloqueig d'escriptor és compartit pel servidor. Sense aquestes variables MySQL, els tests de base de dades s'ometen. L'avís Starlette/TestClient per httpx és conegut; no s'ha instal·lat un segon client HTTP per silenciar-lo.

## Interfície i retirada de l'entorn temporal

```bash
.venv/bin/python -m uvicorn src.web.app:app --host 127.0.0.1 --port 18080
```

Obrir el [panell temporal](http://127.0.0.1:18080). La web usa la data actual d'Europe/Madrid: una revisió futura pot variar la finestra mensual i l'estoc baix respecte a l'informe congelat. Comprovar gràfic, taula mensual, cerca `destornillador` amb `Herramienta manual`, netejar i paginar. No necessita connectar-se a Make.

En acabar, parar Uvicorn amb `Ctrl+C` i retirar **només aquests contenidors temporals**; el tmpfs desapareix:

```bash
docker compose -p nortesur-f12 -f docs/validation/compose.yml down
unset DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD STOCK_API_URL STOCK_API_TOKEN MAKE_WEBHOOK_URL
```

No esborrar volums d'altres instal·lacions. Cal guardar l'evidència abans de retirar la base. Make s'acredita amb les proves externes F10; aquest procediment no reenvia correus ni modifica l'escenari.

## Comprovació F14 — 29/09/2026

Commit funcional **`6f03c19`**, Python 3.13.13, Compose 2.38.2 i MySQL 8.0.46. S'ha clonat localment la branca en un directori temporal net i s'ha creat el projecte Compose `nortesur-f14`, amb el mateix fitxer auxiliar i MySQL en tmpfs. La instal·lació existent de l'usuari no s'ha modificat. Els tests han reutilitzat l'entorn Python ja instal·lat; aquesta fase no repeteix la instal·lació de dependències.

`up --wait` ha retornat serveis healthy i el primer `migrate`, executat immediatament i sense espera manual, ha aplicat 001–004. El segon ha retornat «ya aplicadas». Els 24 tests nous cobreixen connexió immediata, els quatre codis transitoris, recuperació fins al sisè intent, esgotament, errors permanents, connexions ordinàries sense reintents, tancament de sessió fallida, logs sanejats i absència de repetició de SQL.

Dues càrregues reals a `f12_real`, amb Make desactivat i data analítica **2026-09-28**, han conservat el negoci. Execucions `3fe395f6-3b49-42ca-abdb-2cb60feca3f2` i `f2e98fd0-491e-46f6-9ccc-22a0bc476f26`; hash de negoci comú:

```text
aa5f25c83a5c489ab30a7d58ac6ab6f529df13eb78f860a84775eb6817a835c6
```

Resultats: **120 comercials, 39 històrics, 358 comandes, 1.101 línies i 216 observacions d'estoc**. Facturació **1.381.450,43**, 269 comandes elegibles, tiquet mitjà **5.135,50**, marge conegut **575.355,92**, cobertura **95,51 %** i 12 productes sota mínims. El script ha verificat integritat, recomptes i recàlcul Decimal independent. Una comparació posterior amb el [JSON F13](../evidence/f13/repeatability.json) ha confirmat igualtat de hashes d'entrada, facturació, marge, tots els mesos, estoc baix i contribucions dels SKU revisats. Cap crida a Make.

La suite completa, executada després de les càrregues a `f4_test_delivery`, ha aprovat **467 tests (416 unitaris + 51 MySQL), sense omissions**, amb un únic avís conegut de deprecació Starlette/TestClient. Ruff i format correctes (43 fitxers Python). Revisats 19 documents Markdown i 56 enllaços o àncores locals, tots vàlids; enunciat, fonts, expressions Make, llicència, captures i informes històrics preservats. Els informes i captures F12/F13 conserven el seu contingut històric; F14 no atribueix una revisió nova del navegador o dels destinataris externs.
