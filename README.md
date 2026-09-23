# Prueba técnica — Integración y Automatizaciones

Hola y gracias por tu interés en Etailers.

Esta prueba busca ver cómo trabajas, no si te sabes una librería de memoria. Es un caso muy parecido a lo que hacemos cada semana: recibir datos de un proveedor y de un ERP en formatos distintos, limpiarlos, cruzarlos y convertirlos en algo que un cliente pueda mirar para tomar decisiones.

**Plazo de entrega:** 7 días naturales o 5 días laborables desde que recibes este repositorio, lo que prefieras.
**Herramientas:** las que quieras, incluida la IA (ver el apartado *Uso de IA*).

---

## El caso

Uno de nuestros clientes es un distribuidor B2B de ferretería. Trabaja con el proveedor *Distribuciones Nortesur SL* y tiene su propio ERP. La información le llega por cuatro sitios distintos y ninguno se parece al otro:

| Fuente | Formato | Qué contiene |
|---|---|---|
| `data/proveedor_productos.csv` | CSV, separador `;`, codificación **Latin-1** | Catálogo: SKU, EAN, nombre, marca, categoría, precios, IVA, peso |
| `data/tarifas_proveedor.xml` | XML, UTF-8 | Descuentos por categoría y marca, más precios netos pactados para SKUs concretos |
| `data/pedidos_historico.csv` | CSV, separador `,`, **UTF-8 con BOM** | Líneas de pedido desde abril de 2025: cliente, canal, estado, SKU, cantidad, precio y descuento |
| `http://localhost:3001/api/v1/stock` | API REST paginada, con token | Stock por almacén, con fecha de última actualización |

El cliente quiere un proceso que consolide todo eso en su base de datos, un panel donde ver cómo va el negocio, y un aviso automático cuando algo se tuerza.

> Los ficheros vienen tal cual nos los mandan. Sí, están sucios. Esa es justamente la parte interesante.

---

## Qué tienes que construir

### 1. Un proceso de integración (ETL)

Que lea las cuatro fuentes, las normalice, las cruce y cargue el resultado en MySQL.

Algunas cosas que te vas a encontrar y que tendrás que decidir cómo resolver:

- Cada fichero viene en una codificación distinta y hay que cruzar textos entre ellos.
- Precios con coma decimal, con símbolo de moneda, con separador de miles.
- EANs con espacios, con comillas, convertidos a notación científica por Excel, o directamente inválidos.
- Filas duplicadas y SKUs repetidos con precios diferentes.
- Filas con más o menos columnas de las que tocan.
- Fechas en varios formatos, algunas con hora y otras vacías.
- Campos vacíos y centinelas variados: `N/D`, `NULL`, `-`, `n/a`.
- Descuentos que a veces vienen como `10%` y a veces como `0,1`.
- Cantidades negativas, estados escritos de seis maneras distintas y canales sin normalizar.
- SKUs que están en una fuente pero no en las otras.
- Una API que a veces devuelve error 500, que limita las peticiones por minuto y que pagina.

No te pedimos que resuelvas todos los casos. Te pedimos que **decidas conscientemente** qué haces con cada uno y que lo dejes escrito.

### 2. Un modelo de datos relacionado

Como mínimo necesitas:

- Una tabla de **productos** con su precio neto de compra, su PVP y su stock consolidado.
- Una tabla de **pedidos** (cabeceras) y otra de **líneas de pedido**, o el diseño que consideres mejor si lo justificas.
- La **relación entre pedidos y productos**, con claves foráneas de verdad.
- Una tabla de **rechazos** donde quede registrado todo lo que no entró: qué fila era, de qué fuente venía y por qué se descartó. Si un día el cliente pregunta "¿por qué falta este producto?", esa tabla es la respuesta.

Ojo con un detalle: hay líneas de pedido que apuntan a SKUs que ya no están en el catálogo. Decide qué haces con ellas, porque si pones una clave foránea estricta, la carga te va a fallar.

### 3. El precio neto de compra

Para cada producto, calcula el precio neto aplicando, en este orden:

1. Si el SKU aparece en `<Excepciones>` del XML, ese precio manda y no se aplica nada más.
2. Si no, parte del `precio_coste` del CSV y aplica el descuento de categoría más el de marca.

Si dos reglas se pisan o algo no está claro, decide tú y explica el criterio.

### 4. Un panel de negocio

Una página web sencilla (o un endpoint que la alimente) con dos partes:

**Catálogo:** listado con nombre, SKU, precio neto, PVP, stock total y categoría, con filtro por categoría y búsqueda por texto.

**Estadísticas del negocio**, todas ellas cruzando pedidos con productos:

- **Un gráfico de evolución mensual** de facturación y de unidades vendidas, desde abril de 2025 hasta hoy. Debe verse la estacionalidad: el verano y la campaña de otoño se notan en los datos.
- Facturación total, número de pedidos y ticket medio.
- Ventas por canal (B2B, B2C, marketplace).
- Top 10 de productos por facturación.
- Ventas por categoría de producto.
- **Margen bruto**: la diferencia entre lo que se vendió y el precio neto de compra de esos productos. Esta métrica solo sale si las dos tablas están bien relacionadas, y es la que más le interesa al cliente.
- Productos con stock por debajo de 5 unidades que hayan tenido ventas en los últimos 3 meses.

Decide qué pedidos cuentan como facturación. Hay cancelados, devueltos y pendientes, y meterlos todos en el mismo saco da una cifra que no es real.

Para el gráfico puedes usar Chart.js, Recharts, ApexCharts o lo que prefieras. No busques diseño bonito, busca que se entienda y que los números cuadren.

### 5. Una automatización en Make (obligatorio)

Además del ETL, monta un escenario en [Make](https://www.make.com). El plan gratuito es suficiente para esto.

El escenario tiene que hacer algo **útil y conectado con el resto**, no un "hola mundo". La idea: cuando el ETL termina, envía un resumen de la ejecución a un webhook de Make, y Make se encarga de distribuirlo.

Un montaje que funciona bien:

1. **Webhook** que recibe el resumen del ETL en JSON: productos cargados, rechazados por motivo, facturación del último mes, productos bajo mínimos.
2. **Router o filtro** que separe la ejecución normal de la que tiene problemas.
3. Si hay rechazos por encima de un umbral o productos bajo mínimos, **envía un email de alerta** con el detalle.
4. En cualquier caso, **registra la ejecución** en una hoja de Google Sheets o en un Airtable, para tener histórico.

Puedes cambiar el diseño si se te ocurre algo mejor, siempre que tenga sentido de negocio y use al menos un webhook, un filtro o router, y dos módulos de destino.

En la entrega incluye:

- El **blueprint exportado** del escenario (`.json`), dentro de una carpeta `make/` del repositorio.
- Capturas del escenario montado y de una ejecución correcta.
- Una explicación de qué dispara el escenario y qué decisiones toma.
- Si tu escenario recibe datos de tu ETL, el código que hace esa llamada.

### 6. Que se pueda ejecutar dos veces

Si lanzas el proceso dos veces seguidas, el resultado debe ser el mismo. Nada de productos ni pedidos duplicados en la segunda pasada.

### 7. Documentación

Un `SOLUCION.md` en la raíz del repositorio con:

- Cómo se levanta y se ejecuta, paso a paso, desde cero.
- El esquema de base de datos y por qué lo has diseñado así, incluidas las relaciones.
- Las decisiones que has tomado con los datos sucios y qué has descartado.
- Qué pedidos cuentas como facturación y por qué.
- Cómo funciona tu escenario de Make.
- Qué harías distinto si el histórico tuviera 5 millones de líneas de pedido.
- Qué dejaste fuera por tiempo.

---

## Lo que nos gustaría ver si te da tiempo

No es obligatorio. Prioriza que lo anterior funcione bien:

- Reintentos con espera creciente cuando la API falla.
- Carga incremental usando el parámetro `updated_since` de la API.
- Tests de las funciones de normalización.
- Todo el proceso dockerizado.
- Logs con nivel y contexto, en vez de `print`.
- Comparativa año contra año en el gráfico de evolución.

---

## Cómo arrancar el entorno

Necesitas Docker instalado.

```bash
cp .env.example .env
docker compose up -d
```

Eso te levanta:

- **MySQL 8** en `localhost:3307` — base `catalogo`, usuario `etailers`, contraseña `etailers`.
- **API de stock** en `localhost:3001`.

Comprueba que la API responde:

```bash
curl http://localhost:3001/health

curl -H "Authorization: Bearer etailers-demo-token" \
  "http://localhost:3001/api/v1/stock?page=1&per_page=5"
```

La API devuelve un objeto con `data` y `meta`. En `meta` tienes `page`, `total_pages` y `has_next`.

La base de datos arranca **vacía a propósito**. El esquema lo diseñas tú.

---

## Uso de IA

Usa Claude, ChatGPT, Copilot o lo que uses normalmente. Aquí también trabajamos así y no tiene sentido evaluarte en unas condiciones que no son las reales.

La IA escribiendo el código es normal. La IA tomando las decisiones de arquitectura por ti se nota enseguida y es justo lo que no buscamos.

---

## Entrega

### El repositorio

Crea un repositorio en **GitHub** (público, o privado dándonos acceso). Queremos ver cómo trabajas con Git, así que no vale subir todo en un único commit al final.

Requisitos mínimos:

- **Al menos tres ramas de trabajo** además de `main`, con nombres que digan algo (`feature/etl-productos`, `feature/pedidos`, `feature/dashboard`, `feature/make-webhook`...).
- **Commits pequeños y con mensajes descriptivos.** "cambios", "fix" o "wip" repetidos veinte veces no cuentan. Queremos poder leer la historia del proyecto y entender por dónde fuiste.
- **Al menos dos Pull Requests** de rama a `main`, aunque te las apruebes tú. Escribe una descripción breve en cada una.
- `main` debe quedar con la versión que funciona.
- Un `.gitignore` que evite subir `.env`, `node_modules/` o dependencias.
- No subas credenciales reales de Make, Google o cualquier otro servicio.

### El correo

Cuando termines, envía un email a **enric.garcia@theetailers.com** con el asunto:

`Prueba técnica — Integración y Automatizaciones — [Tu nombre]`

En el cuerpo, incluye:

1. El **enlace al repositorio** de GitHub (y acceso si es privado).
2. Un **resumen de dos o tres párrafos**: qué has construido, qué decisiones te costaron más y qué dejaste fuera.
3. Una **captura del panel** con el gráfico de evolución funcionando.
4. Una **captura del escenario de Make** y de una ejecución correcta.

---

Preferimos un proyecto pequeño que funcione y esté bien explicado, a uno enorme a medio terminar.

Si algo del enunciado no se entiende o te bloqueas con el entorno, escríbenos. Preguntar no penaliza.

Suerte.
