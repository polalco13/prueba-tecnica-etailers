# Reglas para agentes de este repositorio

## Alcance y principios

- Antes de implementar, leer completos `README.md`, `PRD.md`, `TECH_SPEC.md`, `DATA_RULES.md` e `IMPLEMENTATION_PLAN.md`; consultar ADR y SOLUCION cuando afecten a la tarea.
- README es la fuente de requisitos. Distinguir requisito explícito, propuesta técnica y supuesto por validar. La planificación no es evidencia de implementación ni confirmación comercial.
- Trabajar únicamente en la fase/tarea solicitada. No implementar fases futuras por iniciativa propia ni confundir una petición de planificación con permiso de implementar.
- No modificar originales de `data/`, no inventar datos ni reglas de negocio. Fixtures sintéticas permitidas en tests, claramente identificadas y nunca presentadas como ejecución real.
- Ante ambigüedad, señalarla y seguir las decisiones documentadas. Si contradice un requisito o falta una decisión imprescindible, resolverla explícitamente; no ocultarla en código. Actualizar documentos/ADR/tests cuando cambie una regla.
- Preferir soluciones pequeñas y defendibles. No añadir frameworks o infraestructura sin necesidad demostrada.
- Inspeccionar `git status` y respetar cambios previos del usuario; no revertirlos, incluirlos en commits ni sobrescribirlos por accidente. Nunca ejecutar operaciones destructivas para «limpiar» el entorno.
- La tarea que creó estos documentos es solo de planificación: no crea extractores, normalizadores, SQL, modelos ORM, endpoints, cliente HTTP, webhook ni tests funcionales.

## Python

- Type hints en interfaces y funciones; funciones pequeñas con responsabilidades separadas. Reglas puras separadas de I/O, SQL y HTTP.
- `Decimal` creado desde texto para dinero/porcentajes; `DECIMAL` en MySQL. No float, redondeo ad hoc ni cálculo monetario en frontend.
- Errores explícitos: distinguir campo/fila rechazada de ejecución fallida. Prohibido capturar todo y declarar éxito.
- Logging con nivel y run_id en código productivo, en vez de print. No imprimir payloads sensibles, contraseñas, tokens ni URL completa del webhook.
- Usar biblioteca estándar cuando baste; fijar/documentar dependencias elegidas. El código debe poder explicarse durante una entrevista.

## Base de datos y datos

- Integridad mediante FKs, UNIQUEs y restricciones de BD, además de validaciones Python; nunca desactivar FKs para cargar históricos.
- Scripts/migraciones versionados y aplicación documentada. Los scripts en db/init no actualizan volúmenes existentes.
- Consultas parametrizadas; no interpolar filtros web ni valores de fuentes en SQL.
- Carga transaccional e idempotente según ADR 002. Fallo de extracción completa no publica una instantánea parcial. No tratar stock desconocido como cero ni coste desconocido como gratis.
- Procedencia de incidencias conservada. No cambiar fuentes para hacer pasar tests. No truncar tablas ni borrar volúmenes del usuario; usar BD de pruebas aislada.
- Respetar política de históricos, duplicados, descuentos, devolución, facturación y margen de DATA_RULES/TECH_SPEC. No sustituirla por intuiciones del agente.

## Tests y finalización

- Toda función de normalización y regla de negocio relevante debe tener tests. Casos esperados independientes del código, incluyendo límites y errores.
- Antes de dar una tarea por finalizada: ejecutar tests relacionados y regresiones afectadas, formatting/linting si está configurado y comprobar fases previas. No inventar resultados ni afirmar pruebas no ejecutadas.
- Verificar FKs, transacciones e idempotencia contra MySQL, no asumir que SQLite reproduce el comportamiento.
- Simular HTTP para unit tests; las pruebas reales de API/Make se registran por separado. Congelar fecha y fuentes al comparar repetibilidad.
- En planificación/documentación pura, revisar consistencia, enlaces y trazabilidad; no crear tests funcionales ni levantar servicios solo para aparentar validación.

## Dependencias y configuración

Antes de añadir dependencia externa justificar qué problema resuelve y por qué no basta la biblioteca estándar o una dependencia ya instalada. Documentar decisión y versión; no instalar dos clientes HTTP equivalentes ni introducir ORM/SPA por comodidad.

Secretos y parámetros configurables llegan por entorno. No sobrescribir `.env` existente. Las reglas de negocio permanecen explícitas/versionadas aunque un parámetro operativo sea configurable. No asumir que Compose interpola variables que hoy están escritas literalmente.

## Seguridad

Nunca hardcodear secretos, commitear `.env`, imprimir tokens o incluir credenciales Make/Google. Sanitizar errores, blueprint, capturas y logs. El mock original muestra el token en su arranque: no copiar esa salida a documentación. No acceder a secretos para una revisión documental.

El plan de Make no autoriza por sí solo enviar mensajes: preparar destinatario/contenido y requerir instrucción explícita antes de mandar correos mediante herramientas. Para configurar y ejecutar integraciones usar solo accesos autorizados; no fabricar conexiones, URLs o evidencias. Mantener datos de clientes fuera de fixtures públicas.

## Cambios, Git y comunicación

Antes de un cambio sustancial identificar archivos afectados, razón y criterio de aceptación; esto no obliga a pedir aprobación adicional para una tarea ya autorizada. Tras el cambio resumir qué se modificó, tests realmente ejecutados, decisiones y pendientes.

Seguir ramas/PR por fases de IMPLEMENTATION_PLAN, usar nombres descriptivos con prefijo `codex/` por defecto y commits pequeños. No mezclar cambios ajenos ni fabricar historial. Mantener main funcional para el incremento integrado y no declarar ejercicio completo mientras falten requisitos obligatorios.

Actualizar SOLUCION con evidencia real cuando exista; dejar TBD cuando falte. Terminar al cumplir la tarea solicitada y recomendar el siguiente paso sin ejecutarlo automáticamente.
