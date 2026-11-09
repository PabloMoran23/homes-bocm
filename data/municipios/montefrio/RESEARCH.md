# Montefrío — Granada — INE 18135

Investigación y extracción en vivo: 9 de noviembre de 2026.

## Fuentes oficiales y alcance

- Portal actual del Ayuntamiento: https://montefrio.es/ . Enlaza a la sede electrónica y a su portal de transparencia: https://montefrio.sedelectronica.es/transparency . Este último muestra una carpeta «7. URBANISMO, OBRAS PÚBLICAS, VIVIENDA Y MEDIO AMBIENTE» con 158 elementos, mediante navegación dinámica Wicket. No se ha extraído esa carpeta ni se presenta como cubierta.
- Inventario documental municipal histórico accesible actualmente: https://ayto-montefrio.es/paginas/pgou.htm . Se identifica como Ayuntamiento de Montefrío y describe expresamente el instrumento urbanístico P.G.O.U. de Montefrío, registro autonómico 5446. El dominio histórico en su raíz redirige a turismomontefrio.org; la ruta específica del inventario y el PDF comprobado responden directamente sin redirección. No se confunde este inventario histórico con un registro actual exhaustivo.
- Corroboración autonómica localizada durante la investigación, no extraída por el adaptador: https://www.juntadeandalucia.es/boja/2013/33/89 . Corrección de errores del anuncio relativo al acuerdo de aprobación del PGOU de 28 de marzo de 2012.

Resultado de la fuente implementada: **1 instrumento real y 55 enlaces PDF**, agrupados en un solo registro. Incluye memoria de ordenación, normas, fichas urbanísticas, catálogo y planos. Los planos de infraestructuras y las fichas no se convierten en obras independientes. Se conservan los títulos y URLs de todos los documentos del inventario, sin un límite de registros. El listado estático observado está completo en una página; el parser rechaza enlaces de siguiente página si aparecen.

La fuente advierte que no incluye Memoria General ni Anexos y remite a la Oficina Técnica para consulta completa. La ficha de Lojilla dice «Sin aprobar por la C.P.O.T.U.»: esa advertencia queda retenida en el título documental. No se afirma aprobación de cada ámbito o documento, vigencia actual del plan, ejecución material ni cobertura de modificaciones posteriores. No se incorporan formularios, anuncios de contratación o noticias como proyectos o licencias concedidas.

## Fechas, procedencia y geometría

La descripción se extrae de la introducción del inventario. Los acuerdos se extraen con su órgano según esa introducción: 28 de marzo de 2012, atribuido por la página a la Consejería de Obras Públicas y Vivienda, y 2 de julio de 2012, Pleno municipal. Se conservan como `acuerdos[].fecha_acuerdo`, con URL de procedencia. La atribución se etiqueta `organo_segun_fuente`: no se sustituye por una atribución jurídica deducida de otra publicación. El texto introductorio conserva asimismo la resolución de inscripción de 16/10/2012, que no se convierte en aprobación.

No existe fecha de publicación verificada de esta página: se omiten `fecha`, `fecha_publicacion` y `fecha_aprob` globales. La fecha de investigación tampoco se usa como fecha del instrumento. Sin coordenadas ni geometría inferidas, `geometry_status: unavailable` y `publication_ready: false`. Licencias, ejecución programada y jitter de geocodificación están desactivados en el manifest.

## Implementación y comprobaciones reproducibles

El adaptador descarga el inventario en cada backfill/update; update renueva la instantánea completa. Verifica identidad del instrumento, advertencia de cobertura y presencia de documentos. Rechaza redirecciones del inventario, documentos PDF de otro origen, inventarios vacíos y paginación detectada antes de sustituir la salida. No depende de evidencia local ni de una lista de registros precargados. `portal.adapter` se resuelve con el registro compartido existente, sin modificarlo.

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_montefrio -v`, **6 pruebas correctas**. Comprueban agrupación y duplicados, documentos y procedencia, fechas explícitas y ausencia de fechas inventadas, rechazo de fuente ajena/vacía/paginada, carga del manifest, backfill/update, licencias desactivadas y conservación de salida previa ante redirección.

Extracción real ejecutada mediante `load_manifest('montefrio')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir` local. **1 registro, 55 enlaces documentales**. El filtro compartido de entidades se ejecutó y marcó categoría desconocida sin bloquear; el registro conserva su tipo de planeamiento y no se presenta como clasificado para publicación.

Evidencia local, sin incorporar al código fuente:

- `evidence/proyectos.jsonl`: salida real del adaptador.
- `evidence/validation.json`: recuentos, fuentes, limitaciones y resultado de comprobación documental.
- `evidence/pgou.html`: respuesta fuente capturada por el adaptador.
- `evidence/current.html`, `evidence/transparency.html`: capturas de descubrimiento.
- `evidence/legacy_home.html`: respuesta de la raíz histórica redirigida.
- `evidence/transparency_urbanismo.xml`: respuesta vacía del intento de navegación dinámica; no constituye una extracción de sus 158 elementos.
- `evidence/sample_pdf_prefix.bin`: primeros 1024 bytes de https://ayto-montefrio.es/impresos/tii100.pdf , HTTP 200, `application/pdf`, firma `%PDF` comprobada. No es el documento íntegro; los restantes enlaces no se han verificado individualmente.

No se han utilizado credenciales, bases de datos, publicación, despliegue ni instalación de dependencias.
