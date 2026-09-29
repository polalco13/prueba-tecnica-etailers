# Solución

Integración de cuatro fuentes → MySQL → catálogo y panel. Make registra cada carga completada en Sheets y envía alertas Gmail cuando corresponde. [Repositorio](https://github.com/polalco13/prueba-tecnica-etailers), [enunciado](README.md), [reglas](DATA_RULES.md).

## Cómo levantar desde cero

Docker y Python 3.13; dependencias fijadas, sin ORM ni SPA. Verificado con Python 3.13.13, Compose 2.38.2 y MySQL 8.0.46.

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

Abrir http://127.0.0.1:8000. Compose levanta MySQL en 3307 y stock en 3001 con valores demo literales; cambiar `.env` no reconfigura sus servicios. Aplicar migraciones 001–004 también con Make desactivado: `db/init` no actualiza volúmenes. No borrar datos para actualizar. La web lee la última publicación, sin ejecutar ETL ni enviar notificaciones.

## Esquema y ejecución

| Tabla | Relación y finalidad |
| --- | --- |
| products | SKU único, coste neto/PVP/categoría y stock nullable. |
| orders / order_lines | Cabecera por ID y líneas con FKs a pedido/producto; firma única. |
| stock_by_warehouse | Una observación por producto/almacén, con FK. |
| etl_runs / rejections | Ejecución y sus incidencias, fuente, fila, acción y motivo. |

Dinero Decimal/DECIMAL; FKs, UNIQUE y CHECKs reales. SKU ausente/rechazado de catálogo conserva sus ventas mediante histórico con costes/stock NULL. [Arquitectura](TECH_SPEC.md).

Extraer/validar antes de publicar las cuatro fuentes en una transacción. Un fallo conserva la publicación anterior; lock MySQL excluye escritores simultáneos. Repetir sincroniza la instantánea sin duplicar negocio; auditoría crece. Sin ID de línea ERP, dos líneas legítimas idénticas son indistinguibles.

Salida 0: publicación con Make desactivado/aceptado HTTP; 1: fallo ETL; 2: negocio publicado sin entrega confirmada. Un run running tras caída requiere revisión. Recuperar notificación con `python -m src.etl --resend-make RUN_ID`; un accepted requiere `--force`, después de revisar Make.

## Decisiones sobre los datos

CSV catálogo Latin-1/`;`, pedidos UTF-8 BOM/coma y XML UTF-8; lectores respetan comillas. Columnas incorrectas rechazan fila; archivo ilegible falla ejecución. Centinelas son NULL; dinero ambiguo se rechaza. EAN inválido/científico y opcionales inválidos descartan campo, sin reconstruir códigos. Peso cero sigue siendo cero.

Un único `?` monetario final del catálogo se recupera con original auditado: `60,56?` → 60.56. No se borran interrogantes interiores ni se relajan pedidos/XML.

Excepción XML manda; ausente: `coste × (1−descuento categoría−descuento marca)`. Antes de elegir SKU, rechazar coste neto > PVP. Entre candidatos válidos, conservar primero del CSV y auditar alternativas; el orden no demuestra actualidad. PRV-2013/2061 usan las alternativas coherentes existentes. PRV-2104 mantiene dos alternativas plausibles, pendientes del proveedor. No imputar costes para obtener margen positivo.

Cabeceras coherentes por pedido; vacíos heredan un único valor y cliente compara mayúsculas sin unir nombres similares. Descuentos `10%`/`10`/`0,1` son 10%; `1` es 1%. Cantidad cero/fraccionaria se rechaza, negativa solo DEVUELTO. Parciales conservan líneas válidas; duplicados por firma. Stock físico suma almacenes válidos, reservas separadas; ausencia/invalidez es NULL. API completa con reintentos 500/429 y Retry-After.

## Facturación y margen

Facturación operativa: ENVIADO/COMPLETADO y líneas positivas aceptadas desde abril de 2025. Importe tras descuento de línea, redondeado a céntimos con ROUND_HALF_UP antes de sumar. Excluir pendientes/cancelados/devueltos; conservar devoluciones sin compensar una venta no vinculada.

Margen: ventas menos coste neto actual de sus productos, coste extendido redondeado por línea. Ventas sin coste/cobertura visibles; no tratar desconocido como gratis. Una venta por debajo del coste puede seguir dando pérdidas. EUR/base fiscal y coste histórico no confirmados.

Panel con evolución/unidades, KPIs, desgloses, rankings y tabla mensual sin JavaScript. Bajo mínimos: físico conocido <5 y venta elegible en tres meses naturales inclusivos. Búsqueda/categoría/paginación solo filtran catálogo.

## Make

Resumen congelado al publicar; POST después del commit. Sheets busca run_id antes de insertar. Gmail alerta si rechazos > umbral (inicial 0) o bajo stock, y marca email_sent_at. Duplicados/normalizaciones no inflan rechazos. HTTP 2xx acredita recepción; destinos se verifican aparte. [Blueprint, configuración y límites](make/README.md).

## Verificación realizada

29/09/2026, reglas v3, fecha analítica 28/09/2026, fuentes originales y MySQL aislado: dos cargas iguales, FKs/contadores correctos, Make desactivado. **120 comerciales + 39 históricos, 358 pedidos y 1.101 líneas**.

Facturación **1.381.450,43**, 269 pedidos elegibles, ticket **5.135,50**, margen conocido **575.355,92**, cobertura **95,51 %**, 12 bajo mínimos. Las ventas/serie mensual coinciden con v2; se corrigen costes y recuperan cinco productos. Recálculo Decimal independiente coincidente con SQL. **443 tests aprobados**, ninguno omitido; Ruff/formato correctos. Deprecación Starlette/TestClient conocida. [Informe y comparación](docs/evidence/f13/README.md), [capturas](docs/evidence/README.md).

Ejemplo: catálogo PRV-2013, coste `318.52 × 0.82 = 261.1864`. Pedido fila 345: `2 × 509.79 = 1019.58`; coste 522.37; margen 497.21. Rechazos consultables por run/fuente/SKU sin imprimir clientes.

### Cómo ejecutar tests

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests docs/validation
.venv/bin/ruff format --check src tests docs/validation
```

Sin configuración MySQL se omiten las pruebas de BD. La [guía aislada](docs/validation/README.md) prepara bases separadas; no usar catalogo ni ejecutar pytest junto al ETL en el mismo servidor.

## Escala, límites y entrega

Con cinco millones de líneas, el primer límite previsible es memoria: sustituir materialización por streaming/staging y lotes con índices para cabeceras/firmas; publicar tras validar todo. Medir memoria, filas/s, locks y planes SQL antes de precalcular agregados. Sin benchmark ni SLA prometido; incremental exige contrato de cambios/bajas e ID ERP.

Fuera: incremental, contenedor Python y comparativa anual. Codex ayudó a implementar/verificar; el autor confirmó decisiones y configuró destinos externos. HTTP simulado no se presenta como Make real. La corrección final está integrada en main mediante la [PR 8](https://github.com/polalco13/prueba-tecnica-etailers/pull/8). Correo de entrega no acreditado.
