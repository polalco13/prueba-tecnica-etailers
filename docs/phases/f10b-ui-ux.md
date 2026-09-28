# F10b — Mejora UI/UX de la plataforma ejecutable

**Estado:** implementada, verificada e integrada mediante PR 6 (`aab89b9`). Dependencia: F10 integrada mediante PR 5 (`ff53b1c`). F11 continúa opcional. Las capturas comparativas se conservan en el historial Git; el paquete final usa solo las [capturas de entrega](../evidence/README.md).

Esta fase responde a la petición del usuario de mejorar UI/UX con las skills instaladas. El [README](../../README.md) exige claridad y cifras correctas; la mejora visual es una ampliación solicitada. La implementación y la evidencia se resumen en [SOLUCION](../../SOLUCION.md) y [docs/evidence/f10b](../evidence/f10b/README.md).

## Resultado esperado y límites

Mejorar la aplicación que se puede arrancar y utilizar: reconocer el periodo y las métricas principales, consultar los desgloses y encontrar productos con menos esfuerzo en escritorio y móvil. El entregable incluye código de la web, evidencia auténtica y explicación de las decisiones; una maqueta por sí sola no cierra la fase.

La base existente es FastAPI/Jinja2, CSS/JavaScript nativos y Chart.js local. Mantener esa arquitectura. Las definiciones de [PRD](../../PRD.md), [TECH_SPEC](../../TECH_SPEC.md), [DATA_RULES](../../DATA_RULES.md) y ADR siguen vigentes. No añadir una SPA, nuevas métricas, autenticación, edición de datos ni un proceso de build para mejorar la presentación. Las animaciones, si ayudan, serán breves y respetarán la preferencia de movimiento reducido.

No modificar ETL, consultas analíticas, migraciones, Make, datos originales ni `.env`. Conservar importes y redondeos calculados en SQL/Python; la conversión que Chart.js necesita para dibujar no alimenta los KPIs. Mostrar costes/stock desconocidos, históricos, margen negativo, cobertura, pedidos parciales y supuestos EUR/IVA sin transformarlos en valores o certezas ficticios.

## Superficies y archivos previstos

| Superficie | Mejora a concretar tras la revisión |
| --- | --- |
| Cabecera y recorrido del panel | Periodo, última publicación y acceso claro a análisis y catálogo. |
| KPIs y avisos | Jerarquía de cifras, etiquetas, unidades y relación entre métricas y límites de calidad. |
| Evolución mensual | Lectura de barras/línea y ejes; mes parcial y acceso a importes exactos en la tabla de respaldo. |
| Canales, categorías, margen, top 10 y bajo stock | Tablas legibles, alineación numérica, densidad y señales semánticas que no dependan solo del color. |
| Catálogo | Búsqueda/categoría combinables, filtros activos, limpiar, resultados y paginación comprensibles. |
| Estados | Sin publicación, sin resultados, datos desconocidos y error de conexión/esquema. |

Archivos candidatos: `src/web/templates/base.html`, `index.html`, `error.html`, `src/web/static/styles.css` y `dashboard.js`. Cambiar `src/web/app.py` solo para necesidades de presentación sin alterar contratos de consulta. Usar `tests/integration/test_web.py` cuando el comportamiento afectado necesite cobertura; no crear tests que se limiten a exigir clases CSS. Registrar resultados en [SOLUCION](../../SOLUCION.md) y, si procede, actualizar únicamente la descripción web de TECH_SPEC.

## Skills y proceso de ejecución

Leer los `SKILL.md` instalados al iniciar la fase; sus rutas se resuelven desde el catálogo de skills de la sesión y no se convierten en dependencias de la aplicación.

- **`impeccable`:** guía principal de contexto, revisión y diseño. Aplicar el enfoque `operate`, adecuado a una interfaz de consulta con tablas y tareas frecuentes.
- **`emil-design-eng`:** controles, estados, foco, feedback, consistencia y detalles de interacción. Su revisión de código UI se documentará con la tabla Markdown `Before | After | Why`.
- **`frontend-ui-ux-design`:** referencias de accesibilidad, diseño adaptable y componentes cuando aporten a los problemas detectados. Consultar las pertinentes, sin acumular workflows duplicados.

`design-taste-frontend` se orienta a landing pages/portfolios y excluye dashboards y tablas de datos; no es la guía de esta fase. Las skills GSAP solo tendrían sentido ante una necesidad de animación independiente y explícita; no justifican añadir esa dependencia aquí.

### 1. Contexto y situación inicial

Leer completos los cinco documentos obligatorios de AGENTS, consultar SOLUCION/ADR pertinentes y comprobar `git status`. Inspeccionar la web ejecutable y el código existente antes de elegir cambios. Usar el arranque documentado de Uvicorn, con datos ya publicados; no ejecutar el ETL ni reenviar Make como parte de la revisión visual.

Ejecutar `impeccable context` sobre `src/web/templates/index.html`. La consulta de planificación encontró interfaz existente y ausencia de `PRODUCT.md`/`DESIGN.md`; volver a comprobarlo al ejecutar. La interfaz actual es el punto de partida. Para ajustes acotados, seguir el flujo de refinamiento de la skill. Si se necesita una nueva dirección visual o falta contexto esencial, seguir `init`/`shape` según sus instrucciones y obtener las respuestas necesarias antes de sustituirla. No inventar audiencia, marca o preferencias del usuario. Agrupar las preguntas materiales en una ronda breve, sin repetir decisiones ya disponibles.

Guardar una referencia del panel y del catálogo con el mismo dataset, `run_id`, `as_of`, filtros y tamaños de ventana que se usarán después. Las capturas F9 del historial Git sirven de contexto histórico; no equivalen a una nueva captura del estado actual.

### 2. Revisión y propuesta acotada

Preparar una lista priorizada de problemas observados y la mejora concreta de cada uno: qué tarea facilita, qué superficie afecta y cómo se comprobará. Distinguir bloqueos de uso, dificultades de lectura y preferencias estéticas. Definir una dirección coherente de tipografía, espaciado, colores semánticos y patrones de controles a partir de esa revisión. Reutilizar tokens CSS y componentes existentes cuando sea posible.

Documentar la propuesta en esta guía o en el brief que requiera la skill. `PRODUCT.md`/`DESIGN.md` solo se crearán mediante el flujo correspondiente si se necesitan; no registrar como confirmadas hipótesis de producto ni como aprobadas decisiones no consultadas. Evitar varias propuestas y entrevistas sucesivas cuando una mejora acotada ya puede ejecutarse.

### 3. Implementación en la aplicación

Leer `craft-floor.md` de impeccable y las referencias pertinentes inmediatamente antes de editar UI. Implementar el conjunto priorizado en plantillas/estilos y comportamiento necesario. Conservar HTML semántico, etiquetas de formulario, escape, enlaces y controles nativos; mantener disponible la tabla mensual sin JavaScript. Los filtros siguen afectando solo al catálogo y la paginación conserva búsqueda/categoría.

No añadir controles decorativos que no funcionen, imágenes generadas de resultados, cifras de ejemplo en la vista real, pantallas de carga ficticias ni métricas calculadas en el navegador. Si aparece una necesidad fuera del alcance, documentarla por separado sin ejecutarla.

### 4. Verificación y cierre

Realizar una revisión conjunta de escritorio y móvil, corregir hallazgos como conjunto y hacer como máximo una ronda de confirmación. Continuar únicamente si quedan fallos concretos o un nuevo cambio invalida una comprobación. Ejecutar una vez el detector de impeccable sobre los objetivos UI modificados según las instrucciones instaladas y revisar sus hallazgos en contexto.

Registrar solo verificaciones realizadas, con entorno/dataset y límites. Actualizar SOLUCION con capturas comparables, decisiones, criterios cumplidos y pendientes. Cerrar cuando se cumpla la aceptación; no ampliar a nuevas rondas estéticas ni avanzar a F11/F12.

## Criterios de aceptación

| ID | Resultado comprobable |
| --- | --- |
| UX01 | En la vista inicial se identifican periodo, última publicación y KPIs; los avisos de cobertura/calidad y supuestos económicos se localizan junto a la información que condicionan. Se puede llegar al catálogo y a los análisis sin adivinar controles. |
| UX02 | Todas las métricas y columnas requeridas de R08–R13 siguen disponibles. Sobre la misma publicación, cifras y periodos coinciden antes/después; el gráfico distingue unidades e importe y la tabla mensual exacta funciona sin JavaScript. |
| UX03 | Buscar texto y categoría juntos, reconocer los valores activos, limpiar y cambiar de página funcionan en la web ejecutable. La paginación conserva ambos filtros y se entiende que no afectan a las estadísticas generales. |
| UX04 | En escritorio y móvil no hay solapamientos, texto cortado ni scroll horizontal de toda la página. Las tablas anchas pueden desplazarse dentro de su contenedor sin ocultar permanentemente datos obligatorios; controles y números son legibles. |
| UX05 | Formulario, navegación, paginación y tabla desplegable son utilizables con teclado, con etiquetas y foco visible, sin trampas. La información no depende solo del color; revisar contraste de textos/controles y ampliación del texto. Movimiento reducido respetado si se añade animación. |
| UX06 | Vacíos, ausencia de publicación y error controlado tienen mensajes y acciones pertinentes. Stock desconocido/invalidado, cero conocido, históricos y límites del margen siguen diferenciados. Hay evidencia visual real y registro de la revisión de cambios indicada. |

## Verificación proporcionada

Una sesión de navegador cubrirá el recorrido principal: periodo/KPIs → evolución y tabla mensual → desgloses/inventario → búsqueda + categoría → limpiar → paginación. Propuesta de tamaños comparables: escritorio 1440 × 900 y móvil 390 × 844. En esa misma sesión comprobar teclado, ampliación de texto, consola y tabla mensual sin JavaScript. Registrar los tamaños realmente usados.

Los estados no disponibles en el dataset real se comprobarán con las fixtures existentes en entorno aislado, identificadas como sintéticas, sin cambiar datos del usuario para producirlos. No afirmar una auditoría completa de accesibilidad a partir de esta revisión acotada.

Se ejecutaron las regresiones web afectadas contra MySQL aislado siguiendo [la guía de tests](../../SOLUCION.md#cómo-ejecutar-tests), junto con lint/formato y una revisión de navegador. No se repitió la suite ETL/Make, ni se enviaron correos ni se hicieron cargas reales por cambios de presentación. La evidencia y los límites están en [docs/evidence/f10b](../evidence/f10b/README.md).

## Entregables y solicitud preparada

- Mejoras implementadas en la web y resumen de problemas resueltos con su motivo.
- Revisión `Before | After | Why` y resultado de UX01–UX06, indicando límites reales.
- Capturas auténticas antes/después y registro de publicación, filtros, tamaños y comprobaciones. Las comparativas realizadas están en el historial Git; la entrega conserva una captura final. Sin secretos ni datos de clientes, ni imágenes editadas para fingir evidencia.
- SOLUCION actualizada y diff revisable de la fase. Rama/PR e integración en `main` cuando se solicite el trabajo Git, sin fabricar historial ni números de PR.

Solicitud para comenzar en un turno posterior:

> Implementa únicamente F10b según `docs/phases/f10b-ui-ux.md` e `IMPLEMENTATION_PLAN.md`, siguiendo AGENTS. Usa impeccable como guía principal y emil-design-eng para interacción y detalles; apóyate en frontend-ui-ux-design cuando proceda. Revisa primero la aplicación ejecutable, concreta las mejoras y aplícalas sobre FastAPI/Jinja2 y los recursos actuales. Conserva los datos, las métricas y reglas existentes. Realiza la verificación acotada indicada y registra evidencia auténtica en SOLUCION. No avances a F11 ni F12.
