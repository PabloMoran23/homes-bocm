# Esporles — INE 07020, Illes Balears

Verificación en vivo: 2026-11-09. Un único adaptador municipal, sin licencias,
programación ni geocodificación artificial.

## Inventario oficial y alcance

Entrada: https://esporles.cat/ca/arxius-i-documents/urbanisme (HTTP 200).
Es el archivo de Urbanisme enlazado en la navegación municipal, no una noticia
seleccionada como semilla. Se descubren desde allí las carpetas de Normativa y
del estudio de detalle de la calle de la Llum. Dentro de Normativa se descubren
los instrumentos y se recorren sus carpetas de documentación escrita/gráfica y
las fichas documentales. No se siguen menús laterales, formularios, enlaces de
impresión ni feeds. No se extraen los anuncios sueltos de Urbanisme.

Inventarios descubiertos:

- https://esporles.cat/ca/arxius-i-documents/normativa
- https://esporles.cat/ca/arxius-i-documents/normes-subsidiaries-0
- https://esporles.cat/ca/arxius-i-documents/adaptacio-de-les-normes-subsidiaries-al-pla-territorial-0
- https://esporles.cat/ca/arxius-i-documents/cataleg-de-patrimoni-historic
- https://esporles.cat/ca/arxius-i-documents/aprovacio-inicial-estudi-de-detall-c-de-la-llum-0

Resultado real: **7 registros, 118 enlaces documentales, 20 páginas HTML**.

| Instrumento o modificación | Documentos |
| --- | ---: |
| Normes Subsidiàries | 35 |
| Adaptació de les Normes Subsidiàries al Pla Territorial | 45 |
| Catàleg de Patrimoni Històric | 13 |
| Modificació límits UA4, març 2015 | 1 |
| Aprovació definitiva de la modificació puntual de les NNSS | 1 |
| Modificació de la fixa AC68B del Catàleg de Patrimoni Històric | 20 |
| Aprovació inicial estudi de detall c/ de la Llum | 3 |

Las memorias, planos, normas, informes y publicaciones de un mismo instrumento
se agrupan, deduplicando por URL y manteniendo cada página de procedencia en
`documentos[].fuentes`. Las modificaciones tienen registro propio y
`instrumento_padre_url`. Los dos conjuntos del catálogo (catálogo y cumplimiento
de prescripciones) pertenecen al mismo instrumento. Los documentos de distinta
etapa no se presentan como obras adicionales ni como versiones equivalentes.
Los identificadores dependen de la URL municipal de la carpeta o modificación.

## Fechas, estados y límites

La descripción municipal de NNSS identifica expresamente aprobación definitiva
23/11/2001 y BOIB 22/12/2001: se extraen en `fecha_aprob` y
`fecha_publicacion` respectivamente. `fecha_acuerdo` y la fecha genérica quedan
nulas. Las demás fechas exactas quedan nulas: nombres de ficheros y carpetas de
subida no demuestran publicación ni aprobación. Abril de 2011 y febrero de 2012
son referencias mensuales en descripciones, sin invención de un día. El
13/12/2004 corresponde al PTIM insular, no a la adaptación municipal.

Las fases de aprobación inicial del estudio y definitiva de la modificación se
atribuyen expresamente al título municipal. No se afirma que todo el archivo
esté vigente. La propia entrada de Urbanisme enlaza también un anuncio de
revocación de aprobación provisional de NNSS de 21 de marzo de 2013; por ello
la adaptación no recibe una fase jurídica vigente a partir de sus documentos
históricos. La agrupación de los ficheros refleja la clasificación del portal,
sin certificar la vigencia individual de cada versión.

Cobertura parcial: archivo de planeamiento accesible actualmente, con materiales
históricos. No es un censo completo de obras, expedientes, licencias o acuerdos.
Se excluyen los anuncios de actividades, convenios, ampliación de agroturismo y
suspensión de licencias de la entrada principal, cuyo contenido no basta para
clasificarlos automáticamente como proyectos o licencias concedidas.

No había paginación activa en las páginas revisadas. El adaptador recorre todas
las URLs de paginación enlazadas (incluidas las numéricas), con deduplicación.
Una paginación ilegible, nuevas carpetas principales, documentos ausentes,
contenido inesperado o más de 200 páginas provocan error antes de escribir el
resultado. No devuelve un resultado truncado al alcanzar ese límite. Las
actualizaciones refrescan la misma instantánea; no mantienen un histórico de
bajas ni interpretan ausencia como derogación.

## Geometría

El portal enlaza https://sitmun.idelma.cat/urb_esporles como visor de urbanismo.
No se ha verificado una capa vectorial o geometría vinculada a estos registros.
Los planos PDF se conservan como documentos, sin vectorizarlos ni asignar el
centroide municipal. `lat`, `lon` y `geometry` quedan nulos,
`geometry_status=unavailable`, `publication_ready=false`.

## Validación reproducible y evidencia local

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_esporles -v` con ese runtime,
**4 pruebas correctas**. Cubren agrupación/deduplicación y procedencia,
paginación con vuelta a la página anterior, modificaciones independientes,
estabilidad de identificadores, exclusión de noticias/formularios, semántica de
fechas, fechas del PTIM ajeno, rechazo de cambios de fuente y manifest.

Extracción real mediante `load_manifest('esporles')`,
`load_portal_adapter(manifest)` y
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Para capturar HTML se añadió únicamente a la configuración en memoria
`evidence_dir` con la ruta absoluta de `evidence/`; no cambia el manifest.
El filtro compartido de entidades informa 7 categorías desconocidas; no se
fuerza una categoría ni se modifica la política común.

`evidence/proyectos.jsonl` contiene los 7 registros reales.
`evidence/validation.json` conserva recuentos, todas las URLs consultadas,
limitaciones, resultado de pruebas y comprobación HTTP de adjuntos. Se guardaron
las 20 capturas HTML por hash de URL y una muestra documental por instrumento:
7 respuestas HTTP 200, con cabecera binaria PDF o ZIP válida. Los otros adjuntos
se retienen como enlaces publicados y no fueron comprobados individualmente.
Algunos PDFs son escaneados; no se afirma haber extraído su texto ni sus fechas.
La evidencia es local, fuera de los cuatro ficheros fuente de la entrega.

No se han cambiado fuentes compartidas ni dependencias. Licencias y métodos
incrementales de licencias devuelven estado deshabilitado y salida vacía.
`schedule.enabled=false`, `licencias.enabled=false`,
`geocode.jitter_missing=false`.
