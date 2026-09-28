# Plan de producto — Integración y automatizaciones

Estado: F0–F10 implementadas, verificadas e integradas en main; F10b integrada mediante PR 6 (`aab89b9`). F12 implementada y validada en `feature/delivery-docs`, pendiente de integración documental y envío; [evidencia](docs/evidence/f12/README.md). F10 mediante PR 5 (`ff53b1c`), con R14/R15 y A09 acreditados. Recuperación de destinos y ejecución de la copia importada no verificadas; [límites de cierre](make/README.md#cierre-y-límites-de-verificación). Fuente normativa: [README.md](README.md). El plazo indicado allí es de siete días naturales o cinco laborables; las fases son incrementos verificables, no jornadas obligatorias.

En estos documentos, **R** significa requisito explícito del README; **D**, decisión técnica propuesta; **S**, supuesto pendiente de validar. Una propuesta no constituye una regla de negocio confirmada. El encargo de planificación exige tests y mayor detalle de robustez aunque el README los considere extras.

## Contexto

Un distribuidor B2B de ferretería recibe información de Distribuciones Nortesur SL y de su ERP. Necesita consolidar fuentes sucias para consultar catálogo, analizar negocio y recibir avisos útiles:

| Fuente | Contenido y contrato observado |
| --- | --- |
| `data/proveedor_productos.csv` | Catálogo, separado por `;`, Latin-1: SKU, EAN, nombre, marca, categoría, coste, PVP, IVA, peso, fecha de alta y descripción. |
| `data/tarifas_proveedor.xml` | XML UTF-8: descuentos de categoría y marca, excepciones por SKU; también condiciones y descuentos por volumen cuyo uso debe decidirse. |
| `data/pedidos_historico.csv` | CSV con `,`, UTF-8 con BOM: identificador de pedido, fecha, cliente, canal, estado, SKU, cantidad, precio unitario y descuento. Histórico desde abril de 2025. No tiene identificador de línea. |
| API REST de stock | Autenticación Bearer, paginación, SKU y almacén, cantidad, reservado y actualización. Puede devolver 500 y 429. |

## Objetivos

Consolidar las cuatro fuentes, normalizar y limpiar sus datos, cargarlos en un modelo relacionado en MySQL con integridad referencial, calcular el precio neto de compra y hacer trazables los rechazos. Exponer un catálogo y un dashboard comprensibles, conectar una ejecución real con Make y permitir repetir el ETL sin duplicar entidades de negocio.

## Requisitos funcionales

| ID | Área | Requisito y delimitación |
| --- | --- | --- |
| R01 | ETL | Leer, cruzar, normalizar y cargar las cuatro fuentes en MySQL. Documentar conscientemente el tratamiento de los problemas de calidad enumerados en el README; no exige recuperar todos los registros. |
| R02 | Productos | Resolver encodings, centinelas, importes, EAN, fechas, columnas incorrectas y duplicados. Conservar nombre, SKU, precio neto de compra, PVP, categoría y stock consolidado para el catálogo. |
| R03 | Tarifas | La excepción de SKU manda y excluye cualquier descuento adicional. En su ausencia aplicar descuentos de categoría y marca al coste CSV; justificar cómo se combinan y resuelven conflictos. |
| R04 | Stock | Consumir la API autenticada y paginada. Decidir cómo se manejan errores, límites, almacenes y SKUs no presentes en catálogo. No se acepta presentar una lectura incompleta como stock completo. Esta última condición es D de fiabilidad. |
| R05 | Pedidos | Normalizar cabeceras y líneas, fechas, descuentos, cantidades, estados y canales. Decidir qué cuenta como facturación y qué hacer con SKUs históricos ausentes. |
| R06 | Modelo | Productos, pedidos y líneas relacionados mediante FKs reales; tabla de rechazos. Justificar el esquema. |
| R07 | Rechazos | Registrar lo descartado con fuente, fila o identificador y motivo. D: añadir ejecución, código estable, acción, entidad y payload limitado. |
| R08 | Catálogo web | Listado con nombre, SKU, precio neto, PVP, stock total y categoría; filtro por categoría y búsqueda por texto. |
| R09 | Evolución | Gráfico mensual de facturación y unidades desde abril de 2025 hasta hoy; permitir observar estacionalidad sin fabricar ni ajustar cifras. |
| R10 | KPIs | Facturación total, número de pedidos y ticket medio, cruzando pedidos con productos. |
| R11 | Desgloses | Ventas por B2B, B2C y marketplace; top 10 productos por facturación; ventas por categoría. |
| R12 | Margen | Diferencia entre ventas y coste neto de compra de los productos relacionados. D: usar coste disponible actual y mostrar cobertura; no afirmar un coste histórico inexistente. |
| R13 | Bajo stock | Productos con stock inferior a 5 y ventas en los últimos tres meses. D: usar stock físico conocido y ventana móvil, según TECH_SPEC. |
| R14 | Make | Escenario útil conectado con el ETL: al menos un webhook, un filtro o router y dos módulos de destino. Se propone alerta por email e histórico en Google Sheets. |
| R15 | Entrega Make | Blueprint JSON exportado en `make/`, capturas del escenario y ejecución correcta, explicación del disparador y decisiones, y código de llamada desde el ETL. |
| R16 | Idempotencia | Dos ejecuciones seguidas con las mismas entradas deben dejar los mismos datos de negocio, sin duplicar productos ni pedidos. D: los registros de auditoría sí reflejan cada ejecución. |
| R17 | Documentación | `SOLUCION.md`: arranque desde cero, ejecución, esquema y relaciones, decisiones sobre datos y descartes, facturación, Make, escala de cinco millones de líneas y exclusiones por tiempo. |
| R18 | Git | Repositorio GitHub accesible, tres o más ramas de trabajo además de `main`, al menos dos PR a `main`, commits pequeños/descriptivos y `main` funcional. |
| R19 | Secretos | `.gitignore` para `.env`, dependencias y artefactos locales; ninguna credencial real de Make, Google u otros servicios en el repositorio. |
| R20 | Entrega | Preparar enlace/acceso al repositorio, resumen de dos o tres párrafos, captura del gráfico y capturas de Make para el correo con destinatario y asunto indicados en README. El envío no forma parte de esta planificación ni se realiza automáticamente. |

## Requisitos no funcionales

Las siguientes medidas son D para satisfacer una entrega pequeña y defendible:

- Reproducibilidad: dependencias fijadas, esquema versionado y guía comprobada en entorno limpio.
- Mantenibilidad: Python, funciones pequeñas, separación de extracción, reglas, persistencia y presentación; sin infraestructura distribuida.
- Auditabilidad y observabilidad: `etl_runs`, incidencias con procedencia, contadores definidos y logs con contexto sin secretos.
- Idempotencia e integridad: claves naturales/UNIQUE, transacciones y FKs en MySQL, además de validaciones Python.
- Errores explícitos: distinguir fila descartada, campo descartado y fallo de ejecución; no publicar un éxito tras una extracción incompleta.
- Seguridad: configuración por entorno, consultas parametrizadas y HTML escapado. Mantener clientes y payloads fuera de logs públicos.
- Precisión: `Decimal` y `DECIMAL`, política de redondeo documentada; nunca `float` para dinero.
- Tests: los normalizadores y reglas relevantes tendrán pruebas antes de continuar. Son opcionales en README, pero forman parte del plan solicitado.

## Criterios de aceptación

| ID | Verificación prevista | Fase |
| --- | --- | --- |
| A01 | Una ejecución lee las cuatro fuentes reales y deja productos, pedidos, líneas, stock y trazabilidad coherentes. Un fallo total conserva el estado de negocio anterior. | F7 |
| A02 | Con excepción XML se obtiene exactamente el precio pactado; sin excepción se aplica la fórmula documentada y comprobada con casos independientes. | F3–F4 |
| A03 | Cero FKs huérfanas; las líneas históricas válidas apuntan a productos históricos explícitos, con coste desconocido visible. | F6–F7 |
| A04 | Cada fila descartada tiene ejecución, fuente, localizador y motivo. Los campos descartados y duplicados también son auditables sin inflar el conteo de filas rechazadas. | F2–F7 |
| A05 | Segunda ejecución con entradas congeladas: mismos valores y conteos de negocio; auditoría adicional esperada. Corregir una línea y reimportar no conserva su versión antigua. | F6–F7 |
| A06 | Catálogo muestra todas las columnas exigidas; búsqueda y categoría funcionan juntas; stock desconocido se distingue de cero. | F9 |
| A07 | SQL validado antes de interfaz: gráfico con todos los meses, KPIs/desgloses y margen reproducibles a partir de los datos consolidados. Vacíos y costes desconocidos se explican. | F8–F9 |
| A08 | Ranking de bajo stock cumple stock conocido < 5 y ventas elegibles en ventana móvil; no confunde ausencia de stock con cero. | F8 |
| A09 | Una ejecución real del ETL llega a Make; el histórico recibe la ejecución y una condición real o prueba controlada identificada demuestra la alerta. Hay dos destinos, blueprint y capturas sin secretos. | F10 |
| A10 | Una persona puede levantar y ejecutar desde cero siguiendo SOLUCION, sin pasos implícitos; los resultados documentados tienen evidencias reales. | F12 |
| A11 | Historial Git acredita ≥3 ramas de trabajo y ≥2 PR hacia `main`; la entrega final está en `main`, sin secretos ni dependencias versionadas. | F12 |

## Ampliación solicitada: mejora UI/UX

El 27/09/2026 el usuario solicitó una fase intermedia de mejora de la plataforma ejecutable usando las skills de diseño instaladas. Se incorpora **F10b**, después de F10 y antes de F12, con [alcance y aceptación propios](docs/phases/f10b-ui-ux.md). Es una ampliación solicitada, no un requisito nuevo del README; quedó integrada mediante PR 6.

La mejora debe facilitar la lectura de métricas, la navegación, los filtros y la consulta de tablas en escritorio/móvil. Conserva R08–R13 y A06–A08, las definiciones de negocio y las limitaciones visibles; no añade métricas ni modifica ETL/Make. La verificación está registrada en [SOLUCION](SOLUCION.md) y en la evidencia visual de la fase.

## Fuera de alcance

No se propone autenticación multiusuario del dashboard local, ERP completo, gestión de clientes independiente, contabilidad fiscal, logística, predicción, orquestador distribuido ni tiempo real. Tampoco se fabricarán costes históricos, identificadores de línea del ERP o EAN perdidos. Kafka, Spark, Airflow, Kubernetes y microservicios no tienen una necesidad demostrada para esta prueba.

Incremental, dockerización de la aplicación y YoY son opcionales. El manejo básico de errores, los tests y logs se adelantan por decisión del encargo; sus mejoras pueden esperar. Esta fase no crea PR ni envía correos automáticamente; la integración y el cierre de entrega quedan para el paso Git solicitado.

## Supuestos que deben validarse

S1: importes de pedido y coste son EUR y comparables sin IVA; el origen no lo confirma. S2: cada CSV completo es una instantánea autoritativa; no hay identidad estable de línea. S3: se acepta facturación operativa de enviados/completados, excluyendo devoluciones sin vínculo con la venta original. S4: stock total significa suma de `quantity`, no disponibilidad tras reservas. S5: procede descuento aditivo categoría + marca. S6: zona horaria de fechas sin offset por confirmar comercialmente; acceso a Make/Google y destinos ya verificados en F10. Estas decisiones tienen alternativas en TECH_SPEC y DATA_RULES.

## Trazabilidad final con README

Los estados distinguen evidencia técnica ejecutada y trabajo pendiente; no implican confirmación de supuestos comerciales.

| Requisito README | Documento/Fase | Estado |
| --- | --- | --- |
| ETL cuatro fuentes | R01; TECH_SPEC; F1–F7 | Verificado en F7 |
| Codificaciones y datos sucios (precios, EAN, columnas, duplicados, fechas, nulos) | R02/R05; DATA_RULES; F1–F3/F6 | Verificado en F1–F7 |
| Tarifas y prioridad de precio neto | R03; DATA_RULES; F3–F4 | Verificado en F3–F7; semántica comercial pendiente |
| API autenticada, paginación, errores/límites y cruces de SKU | R04; TECH_SPEC; F5 | Verificado en F5–F7 |
| Cantidades, estados, canales y definición de facturación | R05; DATA_RULES; F6/F8 | ETL F6–F7 y SQL F8 verificados; criterio comercial por confirmar |
| MySQL relacionado y productos históricos | R06; TECH_SPEC; ADR 003; F4/F6 | Verificado en F6–F7 |
| Rechazos con fuente, fila y motivo | R07; DATA_RULES; F2–F7 | Verificado en F7 |
| Catálogo, búsqueda y filtro de categoría | R08; TECH_SPEC; F9 | Verificado en MySQL/HTML y navegador |
| Evolución mensual de facturación y unidades desde abril de 2025 | R09; TECH_SPEC; F8–F9 | SQL F8 y web F9 verificados |
| Facturación, pedidos y ticket medio | R10; TECH_SPEC; F8–F9 | SQL F8 y web F9 verificados |
| Canal, top 10 y categoría | R11; TECH_SPEC; F8–F9 | SQL F8 y web F9 verificados |
| Margen bruto | R12; TECH_SPEC; F8–F9 | SQL F8 y web F9 verificados; comparabilidad de costes por confirmar |
| Stock < 5 con ventas en últimos tres meses | R13; TECH_SPEC; F8–F9 | SQL F8 y web F9 verificados |
| Make: webhook, router/filtro y dos destinos | R14; TECH_SPEC; F10 | Cliente probado; Sheets/Gmail completados y correo recibido desde ETL real, además de pruebas sintéticas |
| Make: código, blueprint, explicación y capturas reales | R15; SOLUCION; F10/F12 | F10 integrada mediante PR 5; artefactos disponibles y A09 acreditado, con límites de pruebas externas documentados |
| Idempotencia | R16; ADR 002; F4/F6–F7 | Verificada en F7 con fuentes congeladas |
| SOLUCION.md y análisis de cinco millones de líneas | R17; SOLUCION; F12 | Documentado y comprobado; sin benchmark de 5 M |
| GitHub, ramas, commits, PR y main funcional | R18; IMPLEMENTATION_PLAN; F0–F12 | Repo público, seis ramas/PR integradas y main probado; integración documental F12 pendiente |
| .gitignore y secretos | R19; AGENTS; F0/F12 | Revisión de cambios/historial y artefactos; alcance en evidencia F12 |
| Correo, enlace/acceso, resumen y capturas | R20; SOLUCION; F12 | Borrador, enlace y capturas listos; correo no enviado |
| Reintentos opcionales | TECH_SPEC; base F5, mejoras F11 | Reintentos acotados implementados/probados; mejoras F11 no elegidas |
| Incremental updated_since opcional | TECH_SPEC; F11 | Opcional no elegido |
| Tests opcionales en README, exigidos por este plan | AGENTS; F1–F10/F12 | 397 tests pasan en MySQL aislado |
| Dockerización completa opcional | TECH_SPEC; F11 | Opcional no elegido |
| Logs opcionales en README | TECH_SPEC; base F1, mejoras F11 | Logging con run_id implementado |
| Comparativa YoY opcional | TECH_SPEC; F11 | Opcional no elegido |
| Uso de IA permitido y decisiones explicables | AGENTS; SOLUCION; F12 | Uso y límites documentados; recorrido de un registro incluido en SOLUCION |
