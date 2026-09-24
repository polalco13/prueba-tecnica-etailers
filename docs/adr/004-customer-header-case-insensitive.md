# 004 — Cliente de cabecera sin distinguir mayúsculas

## Estado

Aceptado por el usuario el 24/09/2026: las variantes de mayúsculas/minúsculas corresponden al mismo cliente. Implementado como corrección de F6–F7; evidencia en [SOLUCION](../../SOLUCION.md#resultados-de-ejecución). No introduce una tabla ni una identidad global de clientes.

## Contexto

F6 comparaba literalmente el cliente tras normalizar Unicode y espacios. F7 encontró 81 pedidos con diferencias solo de capitalización: se rechazaban sus 324 filas por `CONFLICTING_ORDER_HEADER`. La regla confundía variaciones de escritura con una contradicción en la cabecera. El usuario confirmó expresamente que representan al mismo cliente.

## Decisión

Dentro de cada pedido, normalizar NFC, extremos/espacios y centinelas como hasta ahora; comparar el cliente no vacío mediante `casefold()`. Conservar como texto de presentación la primera grafía normalizada válida y no vacía, en orden del CSV. No aplicar `title()` ni inventar una capitalización.

Los vacíos heredan esa etiqueta si hay una sola clave equivalente, con el aviso existente `HEADER_VALUE_INHERITED`. Todos vacíos mantienen `NULL`. Dos claves diferentes siguen rechazando la cabecera completa: no se eliminan tildes, puntuación ni palabras y no se hace comparación aproximada. Validar longitud antes de comparar; un valor inválido no se oculta por otra variante válida.

Versionar el cambio de `catalog-stock-orders-v1` a `catalog-stock-orders-v2`. La firma `order-line-v1` no cambia: no incluye cliente. Repetir la validación completa y registrar sus nuevos contadores, conservando la evidencia anterior como histórica.

## Alternativas consideradas

- Comparación literal: produjo rechazos de variantes equivalentes confirmadas.
- Convertir todo a mayúsculas al persistir: innecesario para comparar y pierde la grafía de presentación.
- Quitar tildes o usar similitud: podría unir clientes distintos y excede la confirmación recibida.

## Consecuencias

Las líneas de esas cabeceras pasan a validarse individualmente; no se prometen 324 líneas nuevas, pues pueden existir otros errores o duplicados. Se conserva la política de pedidos parciales. El resultado es determinista con el mismo archivo; reordenar filas equivalentes puede cambiar la grafía mostrada, sin cambiar la firma de línea. La auditoría identifica la versión de reglas y sigue excluyendo nombres de clientes de extractos/logs.
