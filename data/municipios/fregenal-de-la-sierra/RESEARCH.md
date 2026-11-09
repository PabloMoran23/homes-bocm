# Fregenal de la Sierra — INE 06050, Badajoz, Extremadura

Investigación y ejecución: 9 de noviembre de 2026. Un único adaptador municipal.

## Fuentes oficiales descubiertas

- Ayuntamiento: https://www.fregenaldelasierra.es/index.php/ayuntamiento/departamentos-municipales/urbanismo describe las funciones del departamento, pero no identifica por sí solo proyectos o concesiones.
- Descargas municipales: https://www.fregenaldelasierra.es/index.php/ciudadanos/modelos-e-impresos incluye una categoría Urbanismo con cuatro subcategorías y 24 archivos según la lectura web. La descarga directa desde Python devolvió HTTP 403 tanto con www como sin www. No se extraen formularios ni se presentan los archivos encontrados por el buscador como licencias concedidas.
- Inventario autonómico oficial elegido: https://sitex.juntaex.es/SITEX/planeamiento (Junta de Extremadura). El selector público identifica Fregenal con ID interno 75, que **no es su código INE**.
- Consulta usada por la interfaz: POST de lectura a https://sitex.juntaex.es/SITEX/ptofiguras/listadoresultadossigcat con `municipioseleccionado=75`, cabecera XMLHttpRequest. Un GET con ese parámetro no reproduce la consulta: devuelve un selector vacío. El adaptador obtiene el identificador desde el selector por nombre exacto antes de consultar.

## Cobertura y agrupación

La extracción real mediante `load_manifest`, `load_portal_adapter` y `backfill_proyectos` devuelve **68 instrumentos municipales**, incluidos históricos y en tramitación: 45 `Vigente`, 13 `No vigente` y 10 `En trámite`, según SITEX. Incluye normas subsidiarias, revisión, modificaciones, PGM, planes especiales y parciales y estudios de detalle. No equivale a 68 obras físicas ni a aprobaciones actuales. Se excluye expresamente la ficha supramunicipal del Plan Territorial de Tentudía-Sierra Suroeste (38282).

Los dos árboles completos (LSOTEX y anterior a LSOTEX) se sirven en una respuesta sin paginación observada. Se recorren todos sus enlaces, deduplicando por identificador oficial; no hay límite arbitrario de registros. El código rechaza la aparición de controles de paginación para impedir una cobertura truncada si cambia el portal. Un fallo de red, ficha ajena al municipio, estructura no reconocida o inventario vacío cancela la ejecución sin sobrescribir una salida anterior con resultados parciales.

Cada figura produce un registro con ID SITEX estable y referencia oficial. Los **239 enlaces documentales** de trámites, recursos y archivos se conservan dentro de su figura, con título y URL de procedencia, en lugar de emitir un proyecto por PDF. Los enlaces asociados adicionales se conservan en `enlaces_relacionados`. Modificaciones con referencia propia permanecen separadas del plan matriz. Se respeta la diferencia entre número de catálogo y denominación municipal: por ejemplo, `NNSS.R-001.M-042` es la modificación puntual municipal n.º 38. La ficha 38580 tiene el campo Figura urbanística vacío: se usa su encabezado oficial completo «Normas Subsidiarias, revisión 001, Plan Parcial 009 Fregenal de la Sierra», conservando el campo vacío en los metadatos originales.

Ejemplos verificables:

- https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/34816 — revisión de normas subsidiarias.
- https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/39691 — modificación n.º 35, ampliación del polígono industrial frexnense; documentos de memoria y planos agrupados.
- https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40684 — modificación n.º 38 sobre el concepto Reformas.

## Fechas, procedencia y límites

`fecha_aprob` corresponde únicamente al campo explícito `Fecha AD` de SITEX y `fecha_publicacion` a `Fecha de publicación AD`; `date_provenance` conserva esta atribución y la ficha fuente. Las fechas de cada trámite permanecen en `tramites`; no se transforman fechas de publicación, firma o descarga en fechas de acuerdo. No se deduce una fase a partir del estado «Vigente» ni del tipo documental. Los valores ausentes quedan nulos y los metadatos de tabla se conservan en `metadata_fuente`.

Existe una discrepancia conocida: la ficha 40684 indica AD 24/03/2025, mientras el anuncio enlazado en DOE (https://doe.juntaex.es/otrosFormatos/html.php?anio=2025&doe=790o&xml=2025080701) describe el acuerdo plenario como de 25/03/2025. Se conserva la fecha informada por SITEX con procedencia explícita, sin afirmar conciliación con el boletín. No se han revisado todos los PDF ni verificado la vigencia jurídica de cada instrumento. Estados y fechas del registro pueden contener inconsistencias históricas.

Cobertura parcial: inventario municipal de planeamiento de SITEX, no todas las actuaciones del Ayuntamiento, obras públicas o licencias. No se consulta contratación para convertir anuncios en proyectos. No hay registro público verificado de concesiones de licencia, por lo que `licencias.enabled=false`. No se extraen geometrías de los planos ni se inventan coordenadas; todos los registros llevan `geometry_status=unavailable` y `publication_ready=false`. `schedule.enabled=false` y `geocode.jitter_missing=false`.

## Validación reproducible

Runtime preinstalado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_fregenal_de_la_sierra -v`: **10 tests correctos**. Cubren selector exacto, deduplicación y exclusión territorial, cambios de estructura/paginación, fechas distintas y ausentes, identidad municipal, agrupación y aislamiento documental, encabezado oficial cuando falta descripción, manifest y POST de consulta con protección frente a escritura parcial.

Extracción real usando el adaptador resuelto desde el manifest: **68 registros**, anotación de política compartida con estado `ok`. Evidencias locales, no destinadas a commit:

- `evidence/proyectos.jsonl`: salida real completa.
- `evidence/validation.json`: recuento, URLs, parámetros, limitaciones, resumen de tests y comprobación documental.
- `evidence/captures/`: selector, respuesta POST y las 68 fichas HTML.
- `evidence/sample-memoria-39691.pdf` y `evidence/document-check.json`: descarga completa de un documento enlazado de la modificación 35, endpoint https://sitex.juntaex.es/SITEX/ptofiguras/downloaddocumento/12338, HTTP 200, 1.511.669 bytes, tipo servido `application/octet-stream`, firma `%PDF-1.4` válida. No se interpreta este chequeo puntual como verificación de todos los documentos.

No se realizan operaciones de publicación, bases de datos o despliegue.
