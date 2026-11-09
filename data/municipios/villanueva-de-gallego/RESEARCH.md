# Villanueva de Gállego — INE 50288, Zaragoza, Aragón

Comprobación en vivo: 2026-11-09. Adaptador exclusivo del municipio, sin cambios
compartidos, dependencias nuevas ni publicación.

## Descubrimiento y fuentes

La portada oficial https://www.villanuevadegallego.org/ enlaza «Urbanismo» a
https://www.villanuevadegallego.org/ayuntamiento/urbanismo/ . Esta página contiene
un inventario documental PGOU (`nav[aria-label="PGOU"]`), normas consolidadas y,
separadamente, formularios. Es una fuente de instrumentos urbanísticos reales,
no una relación de licencias concedidas. Los impresos quedan excluidos.

El mismo inventario enlaza el archivo oficial autonómico
https://idearagon.aragon.es/archivoSIUa/ , cuyo acceso inicial solicita provincia
y municipio. Se ha consultado como fuente complementaria, pero este adaptador
no extrae sus resultados ni afirma cubrir todo el planeamiento de desarrollo.
La portada también enlaza sede electrónica y transparencia; no se usan como
fuentes de concesiones ni se infiere que sus trámites sean expedientes concedidos.

## Resultado y procedencia

Extracción real mediante `load_manifest` y `load_portal_adapter`:
**11 instrumentos, 62 enlaces documentales**. Un PGOU agrupa 52 documentos
(memoria, infraestructuras, normas, catálogo, planos y normas consolidadas).
Diez modificaciones agrupan un documento PDF/RAR cada una: 4, 5, 6, 7,
10, 11, 12, 13, 14 y 15. Los números 8 y 9 no figuran en este inventario.
La página dice que el texto refundido incluye las modificaciones 1, 2 y 3;
no se crean instrumentos independientes para ellas sin documentación separada.
Las normas consolidadas que incluyen hasta la modificación 15 siguen siendo
un documento del PGOU, sin crear un duodécimo instrumento.

Cada documento conserva rótulo municipal, URL original, formato y página de
procedencia. Los IDs representan el PGOU o el número de modificación, no el
orden de descarga ni un supuesto número de expediente administrativo.
No se transforma cada plano en un proyecto ni se descomprimen los RAR.

La página atribuye al texto refundido un acuerdo del Pleno de **16-03-2009**:
se guarda en `fecha_acuerdo`. Enero de 2009 es la edición del texto refundido.
La fecha técnica de actualización de WordPress y el directorio de subida
`2025/04` no son fechas de publicación del instrumento ni de aprobación.
`fecha_publicacion`, `fecha_aprob`, `fecha` y `fase` quedan nulas. Las modificaciones
tampoco reciben fechas o fases por la mera existencia de un enlace.

Se capturaron y convirtieron a texto los PDF `pgou-3_9` a `pgou-3_12`:

- `pgou-3_9.pdf`: portada y memoria identifican modificación 4, mientras varios
  pies interiores dicen modificación 5. Se conserva el rótulo municipal de 4 y
  se documenta esta inconsistencia; no se corrige silenciosamente el original.
- `pgou-3_10.pdf`: portada de modificación 5, edición agosto de 2013.
- `pgou-3_11.pdf`: sin texto extraíble; no se realizó OCR.
- `pgou-3_12.pdf`: modificación 7, documento de aprobación inicial de noviembre
  de 2015. Esto no permite atribuir un día de acuerdo ni su fase actual.

## Cobertura, paginación y límites

El inventario revisado es estático y no presenta paginación. Se recorren todos
sus enlaces, sin límite numérico ni selección de primeras filas. Si aparece
paginación, un enlace no documental no reconocido, desaparece la memoria o
cambia el contenedor esperado, se produce un error antes de sustituir la salida.
El enlace SIUA reconocido se conserva como referencia complementaria del PGOU.
Actualizaciones hacen una nueva instantánea completa, sin cursor incremental.

geometry_status: unavailable

Los planos PDF son documentos gráficos; no se ha verificado geometría vectorial
por instrumento, CRS ni coordenadas. Los registros mantienen geometría,
latitud y longitud nulas. No se usa el centro municipal ni jitter.
Licencias y programación están deshabilitadas.

El clasificador compartido marca **11 pendientes** y
`adapter_incident / unknown_entity_spike`: su heurística exige identidad de
expediente que el inventario no proporciona en el formato esperado. Se preserva
la anotación en la evidencia y no se inventan referencias para superarla.
La extracción documental funciona, pero esa clasificación requiere revisión
independiente antes de cualquier uso posterior como actividad publicable.

## Validación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_villanueva_de_gallego -v`: cuatro pruebas pasan.
Cubren agrupación de instrumentos/documentos, deduplicación, fechas de acuerdo
frente a publicación, exclusión de formularios, cambios de estructura,
paginación, carga del manifiesto, escritura y actualización idempotente.

Se ejecutó `load_portal_adapter(load_manifest('villanueva-de-gallego')).backfill_proyectos(...)`
contra la web real. Evidencia local sin compromiso de publicación:
`evidence/proyectos.jsonl`, `evidence/validation.json`, HTML de portada y
Urbanismo, cuatro PDF y sus textos, y `evidence/document_checks.json` con
comprobación HTTP HEAD de los 62 enlaces. HEAD solo comprueba disponibilidad
HTTP, no valida exhaustivamente el contenido de todos los documentos.
