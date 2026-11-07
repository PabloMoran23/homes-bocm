# Salobreña — Granada — INE 18173

Investigación y extracción real: 7 de noviembre de 2026.

## Fuentes oficiales descubiertas

- Inventario documental municipal: https://www.ayto-salobrena.es/web/plan-general-de-ordenacion-urbana-2001/
- Sede electrónica municipal: https://salobrena.sedelectronica.es/ (redirige a `/info.0`). Expone accesos al tablón `/board`, transparencia `/transparency` y trámites de obras y urbanismo. Los trámites y certificados no acreditan licencias concedidas. No se implementa extracción de estos accesos ni se afirma cobertura de su tablón.
- Categoría municipal de noticias de urbanismo: https://www.ayto-salobrena.es/web/category/urbanismo/ . Descubierta mediante búsqueda; no forma parte de la extracción. No se convierten anuncios ni noticias en expedientes.

Se revisaron `municipio/manifest.py`, `municipio/adapters/portal.py`, el registro de adaptadores y los ejemplos Chipiona y Manlleu antes de implementar. El manifest carga por el mecanismo existente, sin modificar fuentes compartidas.

## Inventario y unidad de registro

La página oficial presenta el **Plan General de Ordenación Urbana 2001** con cuatro secciones: archivo completo ZIP, documentación textual, fichas urbanísticas y planimetría. La extracción obtiene **un instrumento real con 22 enlaces documentales**: un ZIP y 21 PDF. No son 22 proyectos independientes. En particular, las dos entradas «Lobres» son documentos diferentes en fichas y planimetría: se conservan ambos, con sección, título, URL y procedencia. Se deduplican únicamente URLs idénticas.

El parser exige un bloque municipal `div.post` con el título del plan y su cuerpo `div.entry`, las cuatro secciones documentales y documentos en cada una. Conserva todos sus enlaces; no usa límites de registros ni crea un plan a partir de un enlace de navegación. Los enlaces no documentales o externos en el cuerpo provocan error, evitando una extracción parcial silenciosa ante un cambio de estructura.

La página observada contiene el inventario completo de este instrumento en un único cuerpo sin paginación. El `link rel=next` de la cabecera WordPress apunta a la página distinta «Ponencia de valores de Salobreña 2013»: no es una continuación del PGOU. Se rechazan indicadores de paginación del cuerpo para exigir revisión si cambia la fuente. La actualización vuelve a leer el inventario completo; no utiliza fechas CMS como cursor.

## Semántica y límites

Cobertura deliberadamente parcial: documentación del PGOU 2001 actualmente publicada por el Ayuntamiento. No constituye un inventario completo de modificaciones, instrumentos posteriores, obras o licencias, ni acredita la vigencia jurídica del plan. «2001» es parte del nombre; no se transforma en fecha de aprobación. La ruta de subida `2013/04` tampoco acredita fecha de publicación o acuerdo. `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan a null, sin fase inferida.

Se conservan las URLs HTTP tal como las publica el inventario. La comprobación documental usó explícitamente HTTPS para el mismo archivo, registrando ambas URLs. No se han descargado ni analizado todos los documentos ni extraído geometrías de los planos. Coordenadas y geometría quedan a null, `publication_ready: false`. El anotador compartido clasifica este registro como entidad desconocida; no se altera la política compartida ni se afirma aptitud para publicación.

`licencias.enabled=false`, `schedule.enabled=false`, `geocode.jitter_missing=false`. Las llamadas a licencias fallan explícitamente por no existir un registro de concesiones verificado. La programación está desactivada.

## Verificación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_salobrena -v`: **5 correctas**. Verifican agrupación y conservación sin límite (34 documentos en el fixture), documentos de igual título, deduplicación por URL, rechazo de inventarios vacíos, formularios, secciones incompletas, paginación y enlaces inesperados; comprueban además la carga del manifest y que un fallo HTTP no sobrescribe el resultado anterior.

Extracción real: carga con `load_manifest('salobrena')` y `load_portal_adapter`, configurando `evidence_dir` local, seguida de `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. La red se consulta de nuevo durante esta ejecución; no se reutiliza una lista prefijada ni la captura de investigación como entrada.

Resultado: **1 registro, 22 documentos**. Se conserva `evidence/pgou.html`, la salida real `evidence/proyectos.jsonl` y `evidence/validation.json` con recuento, URLs, limitaciones y comprobaciones. `NORMAS.pdf`, documento enlazado por el inventario, respondió HTTP 200, `application/pdf` y firma `%PDF-`; se capturaron solamente sus primeros 1024 bytes en `evidence/normas-prefix.bin`. No se valida así el resto del archivo ni todos los demás enlaces.

Una primera petición sin User-Agent de navegador devolvió 403; las peticiones con User-Agent explícito (incluida la ejecución real del adaptador) devolvieron 200. Los errores HTTP no se sustituyen por registros sintéticos. Evidencia local excluida de los cuatro archivos fuente entregados. Sin operaciones de publicación, base de datos ni despliegue.
