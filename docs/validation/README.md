# Validación final aislada (F12)

Procedimiento ejecutado el 28/09/2026 desde un **clon nuevo de GitHub**, código funcional `aab89b9`, entorno virtual nuevo y MySQL nuevo. Los archivos de esta carpeta se copiaron desde la rama F12 al clon antes de ejecutar la validación; tras integrar F12 vendrán incluidos. [Resultados](../evidence/f12/README.md).

Esto es una comprobación de entrega, no una nueva arquitectura productiva. No usar la base del usuario para pytest. El Compose auxiliar reutiliza las imágenes y mock originales, cambia nombres/puertos y usa tmpfs para MySQL: no monta `mysql_data`. Requiere Compose >= 2.24.4 por `!override`; verificado con 2.38.2. Las contraseñas de abajo son exclusivamente demo del entorno temporal.

## Instalación y servicios

```bash
git clone https://github.com/polalco13/prueba-tecnica-etailers.git nortesur-validacion
cd nortesur-validacion
test -f .env || cp .env.example .env
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
docker compose -p nortesur-f12 -f docs/validation/compose.yml up -d --wait
curl --fail http://127.0.0.1:13311/health
```

No iniciar este Compose si ya existe una validación `nortesur-f12` en uso. MySQL queda en 13317, stock en 13311; el mock conserva sus 500 aleatorios y límite de peticiones. No copiar sus logs de arranque: contienen el token demo.

En la terminal del clon nuevo:

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

El segundo migrate debe indicar que las cuatro migraciones ya están aplicadas. El script exige inicialmente `f12_real` vacía y Make desactivado; llama al ETL real dos veces, fija `as_of=2026-09-28`, comprueba FKs/contadores, igualdad de negocio y hashes del origen y recalcula importes con Decimal independientemente del SQL analítico. Publica un JSON de evidencia sin clientes ni configuración privada. No es una fixture sintética. Una vez ejecutado, no volver a lanzarlo sobre esa misma base ya cargada.

## Suite completa, de forma secuencial

Crear otra base vacía **en el contenedor temporal**. Los tests administran sus tablas y datos sintéticos; no ejecutarlos contra `f12_real` ni `catalogo`:

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

**No ejecutar pytest mientras esté ejecutándose el ETL** en esta instancia MySQL, aunque las bases tengan nombres distintos. El advisory lock es compartido por servidor; una ejecución concurrente debe ser rechazada. F12 detectó esa colisión en el primer intento de validación y repitió la suite secuencialmente: 397 pruebas aprobadas, ninguna omitida. Permanece un aviso de deprecación Starlette/TestClient por httpx; no se añade otro cliente ni se oculta el aviso.

## Interfaz y limpieza del entorno temporal

```bash
.venv/bin/python -m uvicorn src.web.app:app --host 127.0.0.1 --port 18080
```

Abrir http://127.0.0.1:18080. El dashboard usa la fecha actual de Europe/Madrid: una revisión futura puede variar ventana mensual/bajo stock respecto al informe congelado. Comprobar gráfico, tabla mensual, búsqueda `destornillador` + `Herramienta manual`, limpiar y paginar. No necesita conectarse a Make.

Al terminar, parar Uvicorn con `Ctrl+C` y retirar **solo estos contenedores temporales** (el tmpfs desaparece):

```bash
docker compose -p nortesur-f12 -f docs/validation/compose.yml down
unset DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD STOCK_API_URL STOCK_API_TOKEN MAKE_WEBHOOK_URL
```

No borrar volúmenes de instalaciones ajenas. La evidencia final se guarda antes de retirar esta base. Make se acredita con las pruebas externas ya realizadas en F10; F12 no reenvía correos ni modifica el escenario.
