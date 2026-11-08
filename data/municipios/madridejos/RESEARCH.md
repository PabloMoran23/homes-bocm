# Madridejos — Toledo — INE 45087

Investigación y extracción en vivo: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y alcance

El [portal de transparencia medioambiental y urbanística](https://madridejos.es/madridejos-transparente/informacion-medioambiental-y-urbanistica/)
enlaza el [inventario de normativa urbanística](https://madridejos.es/madridejos-transparente/informacion-medioambiental-y-urbanistica/normativa-vigente-en-materia-de-gestion-urbanistica/).
Esta última página es la fuente del adaptador: lista documental concreta, completa
en una página, sin paginación observada. Se leen todos sus adjuntos, sin límite de
registros. Si aparece paginación, un documento sin clasificación o falta el núcleo
del POM, se rechaza la extracción en lugar de producir una instantánea incompleta.

Resultado: **2 instrumentos, 17 enlaces documentales**:

- POM de Madridejos: 16 documentos agrupados (portada, índice, cinco planos de
  información, seis de ordenación, dos memorias y normativa).
- Modificación puntual nº 2 del POM: un PDF independiente, sin mezclarlo con los
  documentos del instrumento original.

La [memoria justificativa](https://madridejos.es/wp-content/uploads/2019/09/memoria-justificativa.pdf)
confirma en su portada el nombre del POM. La denominación de la ficha matriz se
normaliza a ese nombre; no se convierte cada plano de infraestructura en una obra.
Los identificadores usan la página de inventario y la identidad del instrumento;
las URL de salida son documentos reales. Cada adjunto conserva título, URL y
página municipal de procedencia.

La [página de Urbanismo](https://madridejos.es/urbanismo/) describe servicios,
formularios y competencias. No constituye un registro de licencias concedidas.
No se extraen solicitudes, noticias genéricas ni anuncios de contratación. Este
adaptador cubre únicamente el inventario de planeamiento, no todos los proyectos,
obras, actas o expedientes históricos del municipio. La presencia en el inventario
actual no acredita por sí sola la vigencia jurídica de cada instrumento.

## Fechas y geometría

No se interpretan rutas de subida (2019/09), fechas del CMS ni fechas de redacción
como aprobación. La memoria está fechada en febrero de 2004 y la normativa tiene
una etiqueta de mayo de 2004; ninguna prueba por sí sola la fecha de aprobación.
El [PDF de la modificación nº 2](https://madridejos.es/wp-content/uploads/2019/09/modificacion-n2-pom-1.pdf)
es una copia municipal de una publicación del BOP de Toledo. La revisión manual
de su primera página distingue acuerdo inicial de 27/11/2014, acuerdo definitivo
de 13/03/2015, publicación del acuerdo en DOCM de 10/04/2015 y publicación del
texto en BOP de 06/05/2015. El adaptador no analiza el contenido de PDF y deja
`fecha_acuerdo`, `fecha_aprob` y `fecha_publicacion` a null; no introduce estas
fechas como constantes ni inventa una fase.

Sin coordenadas ni geometría extraída de los planos. `publication_ready=false`;
`licencias.enabled=false`, `schedule.enabled=false` y
`geocode.jitter_missing=false`.

## Validación reproducible

`python -m unittest municipio.test_madridejos -v`: 7 tests correctos con el runtime
indicado. Cubren agrupación, procedencia, guiones tipográficos reales, fechas y
geometría ausentes, exclusión de formularios, deduplicación, paginación, documentos
desconocidos, manifest y conservación de salida anterior ante fallo del parser.

Ejecución real mediante `load_manifest('madridejos')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir=evidence`
solo en la configuración de la ejecución local. Sin publicación ni base de datos.
Los 17 documentos se verifican por HTTP y firma inicial PDF; dos PDF se descargan
completos para revisar sus portadas. El resto solo se comprueba al inicio, sin
analizar íntegramente sus páginas.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json` (recuento, URL, limitaciones y comprobaciones de PDF),
`evidence/inventory.html`, `evidence/transparencia.html`, `evidence/urbanismo.html`
y los dos PDF con sus primeras páginas convertidas a texto. Las pruebas usan
fixtures autocontenidos, no requieren esos archivos locales ni acceso a red.
