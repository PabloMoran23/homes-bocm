# Haro, La Rioja — INE 26071

Investigación y extracción verificadas el 7 de noviembre de 2026. Fuente primaria:
[Servicios municipales / Urbanismo](https://www.haro.org/es/servicios-municipales/urbanismo).
La identificación municipal figura también en el pie oficial: Haro, La Rioja.

## Inventario y alcance

El inventario HTML público contiene 43 enlaces a fichas de planeamiento, todos en
una sola página, sin paginación observada. Se descubren los enlaces y títulos en
cada ejecución; no se usa una noticia fija ni una lista fija de expedientes.
Se recorren 35 fichas de instrumentos discretos: modificaciones del PGM y PEPCHA,
modificación del plan parcial de los sectores S-1.1 a S-1.4, plan parcial del
Sector 5, corrección de error y redelimitación del PERI Gaviota.

Se obtienen **34 instrumentos reales**. Las fichas
[40, aprobación inicial](https://www.haro.org/es/ayuntamiento/urbanismo/40) y
[41, aprobación definitiva](https://www.haro.org/es/ayuntamiento/urbanismo/41)
son fases de la misma 31ª modificación del PGM: producen un registro con ambas
fuentes y sus documentos. La numeración de modificaciones PGM y PEPCHA se mantiene
en series separadas; una modificación conjunta PGM/PEPCHA conserva su primera
numeración PGM y el título completo. Para instrumentos sin ordinal se usa el ID
de ficha municipal, sin presentarlo como número administrativo de expediente.

Cobertura parcial explícita: se excluyen ocho fichas generales (adaptaciones 0.0,
0.1 y 0.2; catálogo general; avance y borrador de revisión; convenios genéricos;
estudio de regeneración). La ficha general titulada «Plan General Municipal de
Haro 2013» mezcla documentación del plan aprobado en 2001 con modificaciones;
no se convierte ese título ambiguo en otro proyecto ni se deduce aprobación en
2013. Se consulta como catálogo complementario:
https://www.haro.org/es/ayuntamiento/urbanismo/1
Sus enlaces identificados por título se asignan a las modificaciones 28ª y 29ª
del PGM y 10ª del PEPCHA, conservando `source_url` del catálogo.

Hay **15 enlaces documentales**, todos comprobados con GET en streaming: HTTP 200
con cabecera de descarga PDF. Los cuerpos de los documentos no se analizan ni se
confunde la disponibilidad del enlace con una validación jurídica del documento.
Ocho instrumentos tienen documentos y 26 sólo ficha descriptiva; se preservan
los enlaces, títulos, descripciones y la procedencia por ficha en `fuentes`.
Los documentos no generan registros separados. El inventario tampoco acredita
que todos estos instrumentos históricos sigan vigentes o se hayan ejecutado.

## Fechas y semántica

Sólo se extraen fechas explícitamente etiquetadas de aprobación definitiva y de
publicación en BOR. Se admiten fechas numéricas y meses españoles, y la errata
original «DEFINTIVA». El estado puede estar acreditado por el título sin fecha:
por ejemplo la 31ª modificación está publicada como aprobación definitiva, pero
no se inventa el día. Las fechas de BOR describen publicación en el boletín según
la ficha, **no** publicación web. `fecha` y `fecha_acuerdo` quedan nulas.
La descripción original retiene también las fases iniciales y provisionales.
No se deducen fechas de años en títulos, nombres de archivos ni cabeceras HTTP.

No se extraen formularios de solicitud, anuncios de contratación, noticias ni
licencias concedidas. `licencias.enabled=false`; ambos métodos de licencias
escriben un archivo vacío con estado `disabled`.

## Geometría y límites operativos

geometry_status: unavailable

El inventario enlaza [IDE Haro](http://www.iderioja.larioja.org/geovisor/index_fs.php?map=HARO).
No se ha verificado una capa vectorial vinculada por identificador a cada ficha.
Los planos PDF enlazados no se convierten en geometría. `lat`, `lon` y `geometry`
quedan nulos, `publication_ready=false`, `geocode.jitter_missing=false` y
`schedule.enabled=false`.

La ejecución actualiza una instantánea completa del alcance seleccionado. Ante
paginación detectada falla explícitamente, sin devolver una primera página como
cobertura completa. También falla ante inventario vacío, títulos desconocidos,
respuesta no HTML, pérdida del contenido esperado o discrepancias inventario/ficha.
No hay estado incremental ni borrados externos. Se espera 0,15 s entre fichas y
se aplica timeout de 35 s por petición. Una ficha sin adjuntos es válida si mantiene
su descripción oficial; no se fabrica documentación para completarla.

## Validación reproducible y evidencias locales

Runtime usado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_haro -v` — cinco pruebas offline:
selección/deduplicación; paginación y cambios de marcado; fechas explícitas;
agrupación de fases y procedencia documental; carga del manifest y actualización.
Los fixtures están en el archivo de pruebas y no dependen de evidencias locales.

La extracción real carga el manifest con `load_manifest('haro')`, resuelve el
adaptador con `load_portal_adapter` y llama a `backfill_proyectos` sobre
`evidence/proyectos.jsonl`, con `portal.config.capture_dir=evidence/captures` sólo
en la ejecución de validación. `evidence/validation.json` incluye recuentos,
URLs, exclusiones, limitaciones, hashes y rutas de capturas HTML. Las comprobaciones
de descarga están en `evidence/document-checks.json`. Evidencias no versionadas.

El anotador compartido de entidades marca los 34 registros como `pendiente` y
reporta `adapter_incident / unknown_entity_spike`: sus reglas requieren referencias
administrativas que estas fichas no publican. Se conserva ese resultado en las
evidencias; no se inventan números de expediente ni se alteran reglas compartidas
para eludirlo. Los datos son revisables como instrumentos municipales reales,
pero necesitan revisión semántica antes de ingestión/publicación.
