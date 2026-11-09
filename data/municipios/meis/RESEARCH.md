# Meis — INE 36028, Pontevedra, Galicia

Comprobación en vivo: 2026-11-09. Un adaptador municipal, sin fuentes compartidas
modificadas. Cobertura parcial de instrumentos de planificación, no de licencias.

## Descubrimiento y fuente vigente

- https://www.meis.gal/ — web oficial, HTTP 200; navegación «Urbanismo».
- https://www.meis.gal/transparencia/ — HTTP 200; «Urbanismo e obras públicas»
  remite a la misma página de Urbanismo.
- https://www.meis.gal/urbanismo/ — HTTP 200; inventario documental actual de
  «Plan Xeral de Ordenación Municipal», «Documentación», «Planos» y plan de movilidad.
  Es la única fuente de registros del adaptador. No es una noticia individual ni
  una lista de resultados prefijada: descubre enlaces e instrumentos del HTML.
- El inventario enlaza
  https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36028.
  Su respuesta directa mostró el selector de concellos, sin fichas de Meis en HTML;
  no se incorporaron supuestos expedientes de ese enlace.
- https://meis.sedelectronica.gal/info.0 apareció en el descubrimiento web con
  catálogo de trámites y tablón. «Comunicación previa obra menor» es un trámite,
  no una licencia concedida. No se ha verificado un registro de concesiones;
  licencias deshabilitadas. Tampoco se usa un anuncio de delegación de competencias
  para convertirlo en aprobación de obras.

## Resultado y agrupación

Extracción en vivo por el adaptador cargado desde el manifest: **5 registros y 22
URLs PDF distintas**, todas comprobadas mediante HTTP y firma `%PDF-`.

| Registro | Documentos | Contenido comprobado |
| --- | --- | --- |
| PXOM de Meis | 18 | PDF principal y 17 planos (2 de suelo urbano y 15 numerados) |
| Modificación puntual 1 del PXOM | 1 | Edicto con orden de aprobación y normativa |
| Modificación puntual 3 del PXOM | 1 | Edicto con orden de aprobación y normativa |
| Modificación puntual 4 del PXOM | 1 | BOPPO con orden de aprobación y normativa |
| Plan de mobilidade sostible de Meis | 1 | Plan municipal completo, no una convocatoria |

Los planos no son proyectos independientes. Las modificaciones son instrumentos
identificables distintos del PXOM; enlaces repetidos se deduplican y documentos
con el mismo número de modificación se agrupan. Se conserva el título del enlace,
URL documental y URL del inventario en cada documento. IDs semánticos estables por
instrumento, independientes de la fecha de subida y posición de los enlaces.

Se descargaron para investigación los cinco documentos principales, conservados
en evidence/: `doc-58.pdf` (PXOM), `doc-59.pdf` (MP1), `doc-60.pdf` (MP3),
`doc-61.pdf` (MP4), `doc-80.pdf` (PMUS). `source_captures.json` relaciona sus URLs,
tamaños y huellas SHA-256. Los `.pdf.txt` contienen las primeras tres páginas
extraídas con pdftotext. Las tres primeras páginas del PXOM escaneado no dieron
texto; el inventario municipal sí identifica su título y sus planos.

No se extraen auditorías de abastecimiento, saneamiento o alumbrado como obras:
una auditoría no demuestra ejecución de actuaciones. Se excluyen navegación,
formularios, contratación y noticias laterales. El PMUS se mantiene como un solo
plan; sus propuestas internas no acreditan proyectos aprobados ni obras ejecutadas.

## Fechas, fase y vigencia

El HTML no ofrece fechas de publicación ni aprobación por instrumento. El parser
no interpreta el texto de los PDF: `fecha`, `fecha_publicacion`, `fecha_acuerdo`,
`fecha_aprob` y `fase` quedan nulos. No utiliza fechas del directorio WordPress,
fecha HTTP ni fecha de descarga como fechas del expediente.

La lectura documental de investigación permite distinguir:

- MP1: orden de aprobación definitiva de 25 de octubre de 2005, mencionada en el
  edicto. No equivale a la subida del fichero en diciembre de 2016.
- MP3: orden de 24 de enero de 2011; tampoco corresponde a la ruta de subida de 2016.
- MP4: orden de 5 de agosto de 2021; el documento cita publicación DOG de 23 de
  agosto y es BOPPO de 7 de octubre de 2021. Son fechas de acuerdo/publicaciones
  diferentes, no una única fecha intercambiable.
- PMUS: edición «MAIO 2022» en su equipo redactor; la ruta de subida es abril de
  2026. Ninguna de ellas acredita un acuerdo de aprobación del PMUS.

Estas observaciones son investigación, no metadatos constantes inyectados en los
registros. La mera presencia en la web no acredita vigencia jurídica, consolidación
ni que no existan otras modificaciones; no se inventa una MP2 ausente del inventario.

## Cobertura, paginación y geometría

Inventario estático sin paginación observada. Se recorre íntegramente su bloque de
PXOM y el enlace municipal al PMUS. Si aparece paginación se falla explícitamente;
no hay un límite de filas que trunque silenciosamente. Fallan cambios de estructura,
ausencia de documento principal/planos, documentos PDF sin clasificar dentro del
bloque PXOM, URLs no municipales o documentos que no respondan como PDF.
Actualización y backfill regeneran la instantánea completa; no representan un
histórico exhaustivo de planeamiento ni de obras municipales.

`geometry_status: unavailable`. Los planos PDF se retienen como documentación,
sin convertirlos a geometría ni asignar un centroide municipal a un instrumento.
No se verificó una capa vectorial con correspondencia por expediente. Coordenadas
y geometría nulas; `publication_ready: false`; `geocode.jitter_missing: false`.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_meis -v`: 6 pruebas correctas. Comprueban
  agrupación, exclusiones, fechas nulas, descubrimiento de otra modificación,
  deduplicación, rechazo de paginación/cambios/URLs externas, manifest y licencias.
- Extracción real: `load_manifest('meis')`, `load_portal_adapter(manifest)`,
  `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`; para capturas,
  `manifest.portal.config['evidence_dir']` se establece localmente antes de cargarlo.
- `evidence/proyectos.jsonl`: 5 registros reales. `evidence/validation.json`:
  recuento, fuentes, limitaciones y resultado del adaptador y política de entidades.
- `evidence/inventory.html` y `document_checks.json`: captura usada por el adaptador
  y verificaciones de todos los documentos. El adaptador solo lee la firma de los
  PDF en cada refresco para evitar descargar repetidamente el PMUS de 218 MB.

Evidencia local excluida de los cambios de código. `schedule.enabled: false`,
`licencias.enabled: false`. Sin publicación, despliegue ni acceso a bases de datos.
