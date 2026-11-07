# La Llagosta — Barcelona — INE 08105

Verificación en vivo: 2026-11-07.

## Descubrimiento y ámbito

La página municipal de Urbanisme enlaza proyectos en exposición pública:
https://www.llagosta.cat/municipi-per-temes/urbanisme

La entrada municipal de información oficial de Urbanisme redirige a esa página:
https://www.llagosta.cat/ajuntament-seu-electronica/informacio-oficial/28-urbanisme

El menú municipal conduce al inventario completo utilizado por el adaptador:
https://www.llagosta.cat/ajuntament-seu-electronica/informacio-oficial/exposicio-publica

Se recorren todas sus filas `li.article-item`, se seleccionan proyectos de obra,
planes directores/estratégicos y el plano de delimitación de prevención de incendios,
y se consulta cada detalle. Se excluyen ordenanzas fiscales, reglamentos,
subvenciones, estatutos y planes de salud. No se extraen noticias ni licitaciones.
La página no tiene paginación en la captura revisada. El parser rechaza enlaces de
paginación o controles nuevos, en lugar de aceptar una extracción truncada.

El portal de transparencia ofrece otras familias de información urbanística:
https://seu-e.cat/ca/web/lallagosta/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme
No forma parte de esta extracción. No se afirma exhaustividad histórica ni
cobertura de todo el planeamiento vigente del RPUC. El ámbito es el inventario
actual de documentos municipales en exposición pública, que puede cambiar.

## Resultado y semántica

11 expedientes/instrumentos reales, 15 enlaces documentales agrupados:

- Sustitución de calderas en centros escolares.
- Mejora del espacio público del núcleo urbano.
- Pla Director del Verd Urbà (3 documentos).
- Plano de delimitación de prevención de incendios forestales (3 documentos).
- Pla Estratègic de Drenatge Urbà Sostenible.
- Proyecto refundido de reforma de piscina de verano del CEM El Turó.
- Reforma de un nuevo casal en Plaça d'Europa.
- Reforma y mejora del Centre Cultural.
- Accesos viarios desde C-17 a la intermodal de La Llagosta.
- Urbanización del carrer de Pablo Picasso.
- Mejora del polígono industrial.

Cada detalle conserva título, descripción municipal, URL de inventario, URL del
detalle y todos los documentos del bloque `#page-documents`, con su procedencia.
Los anexos y planos no generan proyectos adicionales. IDs estables derivados de
la URL del detalle; duplicados de URL se agrupan. No se descargan ni interpretan
los PDF, algunos de gran tamaño; la evidencia capturada es HTML comprimido.

`fecha_publicacion` procede de la fecha de la fila del inventario, nunca de
«Darrera actualització». `fecha_acuerdo` sólo procede de una fecha completa
explícita en la descripción. Los acuerdos del Verd Urbà y del plano de incendios
citan «29 de setembre» sin año: se conservan en la descripción, pero su campo de
fecha queda null. El proyecto C-17 no declara acuerdo: fase y fecha null.
Los otros diez describen aprobación inicial; no se atribuye aprobación definitiva,
ejecución ni licencia concedida. `fecha` y `fecha_aprob` quedan null.

No se ha verificado geometría vinculada a estos instrumentos ni se han
vectorizado planos. `lat`, `lon`, `geometry` null; `geometry_status: unavailable`,
`publication_ready: false`. No se usa centroide municipal ni jitter.
Licencias y ejecución programada deshabilitadas.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```
PYTHONDONTWRITEBYTECODE=1 /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_la_llagosta -v
```

Cinco pruebas verifican fechas y semántica, agrupación y procedencia documental,
rechazo de contenido ajeno/cambiado, rechazo de paginación e instantáneas de
backfill/update con licencias deshabilitadas. La extracción en vivo usa
`load_manifest('la-llagosta')` y `load_portal_adapter`, seguido exclusivamente de
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`. El resultado y URLs están
en `evidence/validation.json`; las capturas `.html.gz` se guardan con un nombre
SHA-256 de la URL (primeros 16 caracteres). Evidencias locales, no fuente.

El disco rechazó temporalmente escrituras durante la investigación; las capturas
se conservaron en `/tmp` y la escritura posterior se completó al liberarse espacio.

## Límite del clasificador compartido

La ejecución a través del registro aplica la política compartida de entidades.
Los 11 registros quedan `pendiente / insufficient_identity_evidence` y el informe
marca `adapter_incident / unknown_entity_spike`: las páginas municipales no
publican un número de expediente que satisfaga esa política. Sus títulos catalanes,
URLs y documentos permiten extraer los instrumentos, pero no otorgan elegibilidad
de actividad en el clasificador actual. Se conserva el resultado íntegro en la
evidencia; no se inventan referencias para sortearlo ni se modifica código común.
Esto requiere revisión independiente antes de cualquier ingestión/publicación.
