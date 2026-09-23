# 003 — Productos históricos mínimos para conservar relaciones

## Estado

Propuesto. Se apoya en la existencia de SKU históricos ausentes indicada por el README; verificar los casos reales durante F6.

## Contexto

El README exige FKs reales entre líneas y productos y advierte de SKU que ya no están en catálogo. Rechazar todas esas líneas reduciría la cobertura del análisis de ventas. El origen no proporciona nombre, categoría ni coste histórico recuperables para esos SKU.

## Decisión

Crear/reutilizar un producto identificado por SKU para cada línea de pedido válida que no tenga producto comercial aceptado. Marcar `is_historical=true`, `in_catalog=false`; campos desconocidos a NULL, sin precio/stock inventados. La etiqueta visual de histórico no se atribuye al proveedor. Registrar procedencia, incluyendo si el SKU estaba ausente o si su fila de catálogo fue rechazada.

Todas las líneas conservan una FK no nula. Históricos contribuyen a ventas; se agrupan como sin categoría si falta ese atributo. Coste desconocido no participa en margen conocido y su facturación queda visible mediante cobertura. No crear productos solo por recibir un SKU desconocido en stock. Si el SKU regresa al catálogo, promover el mismo ID.

## Alternativas consideradas

- Rechazar líneas huérfanas: sencillo y válido si se declara, pero pierde histórico útil.
- FK nullable: permite guardar línea, pero debilita el objetivo de relación real y complica estadísticas.
- Un producto genérico para todos: pierde identidad por SKU y rankings.
- Imputar nombre/coste/PVP desde otros productos: inventa información y distorsiona margen.

## Consecuencias

Los campos que un producto comercial exige serán nullable para históricos con controles coherentes. UI y consultas deben mostrar la distinción, no convertir NULL a cero. El catálogo comercial excluye históricos por defecto; los análisis de pedidos los conservan. El margen es una estimación de la parte con coste actual conocido, no una afirmación sobre rentabilidad histórica completa.
