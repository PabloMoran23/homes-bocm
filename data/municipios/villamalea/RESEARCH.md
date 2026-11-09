# Villamalea — Albacete — INE 02079

Investigación y extracción real: 9 de noviembre de 2026. Python utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se revisaron `municipio/adapters/portal.py`, el cargador de manifiestos, el registro
de adaptadores y el ejemplo de Chipiona antes de implementar este municipio.

## Fuentes oficiales y alcance

El [mapa web municipal](https://villamalea.es/mapa-web/) enlaza dos inventarios
públicos específicos de planeamiento, servidos por el propio Ayuntamiento:

- [Plan de Ordenación Municipal](https://villamalea.es/plan-de-ordenacion-municipal/):
  26 documentos del POM (normas refundidas, cuatro anexos y planos), agrupados en
  un instrumento; un documento de la modificación puntual 20, separado del POM.
- [Modificaciones Puntuales del POM](https://villamalea.es/modificaciones-puntuales-del-pom/):
  modificación 16 (publicación BOP), catálogo de bienes y espacios protegidos
  diligenciado, interpretación C1 y modificación 18. Esta última contiene nueve
  documentos: anuncio de exposición pública, informe técnico, seis partes de
  planos y memoria. Se conserva como un único instrumento, no nueve proyectos.

Resultado en vivo: **6 registros y 39 enlaces documentales**. Cada documento
conserva el texto literal del enlace, URL de descarga y página de procedencia.
Los identificadores corresponden al instrumento, independientes de la URL de
cada PDF. Los documentos del POM original y el catálogo diligenciado posterior
se mantienen separados; no se deduce que tengan idéntica versión o vigencia.
El catálogo posterior se identifica por su título municipal propio.

Las dos páginas actuales son inventarios completos en HTML sin paginación
observada. Se leen todos sus enlaces PDF dentro de los widgets de contenido,
excluyendo navegación y pie. La aparición de controles de paginación provoca
error explícito, sin devolver una primera página incompleta. Una estructura
vacía, título inesperado, host documental desconocido o PDF sin clasificación
provoca error antes de escribir el resultado. No hay límite de registros.

El mapa también enlaza páginas de proyectos IDAE: alumbrado público,
instalaciones fotovoltaicas, aerotermia, rehabilitación de envolvente y dos
instalaciones en el centro dotacional integrado. Se consultaron como fuentes
candidatas y se guardaron capturas locales. Esta implementación limita su
cobertura a los dos inventarios de planeamiento; no extrae aquellas páginas,
noticias, contratación, el tablón Sedipualba ni todo el histórico urbanístico.
[Instancias](https://villamalea.es/instancias/) contiene solicitudes y modelos;
no se utiliza como registro de concesiones. Licencias desactivadas.

## Semántica y límites

Son instrumentos/documentos publicados, sin afirmar concesión de licencia,
aprobación de todo el POM, ejecución de obras ni vigencia jurídica actual.
Los tipos describen el contenido, sin convertirlos en fase de tramitación.
No se generan fechas normalizadas: las carpetas de subida y nombres de ficheros
no prueban publicación ni acuerdo. La cabecera «Modificación 14-05-2025» no se
convierte en aprobación. El título literal del catálogo conserva «Aprobado
definitivamente 10-12-2024», sin confundir ese texto con fecha de publicación.
Se mantienen los anuncios como documentos del instrumento al que pertenecen.

No se extrae geometría de los planos ni se inventan coordenadas. Todos los
registros tienen `publication_ready: false` y `geometry_status: unavailable`.
El clasificador compartido anota los seis registros como `unknown` al no haber
referencias de expediente o identidades de actividad suficientes según sus
reglas; esto se conserva sin inventar números de expediente para sortearlo.
No son actividades listas para publicación. `schedule.enabled`,
`geocode.jitter_missing` y `licencias.enabled` son `false` en el manifiesto.

## Verificación reproducible y evidencia local

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_villamalea -v`

Seis pruebas correctas: agrupación POM/modificaciones, aislamiento del contexto
MP18 y retención de todos sus documentos, deduplicación y exclusión de navegación,
rechazo de vacíos/hosts inesperados/paginación/documentos desconocidos, rechazo
de formularios y contrato de carga del manifiesto/adaptador. Los tests utilizan
HTML sintético pequeño, sin depender de la disponibilidad del servidor.

Extracción real mediante `load_portal_adapter(load_manifest('villamalea'))` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`adapter.config['capture_dir'] = 'evidence'`. La configuración opcional guarda
las respuestas HTML exactas utilizadas; no cambia el resultado del parser.
`update_proyectos` vuelve a obtener el inventario actual completo; no simula
histórico, seguimiento de eliminaciones ni descarga incremental.

Evidencia sin versionar: `evidence/proyectos.jsonl`, `evidence/validation.json`,
las capturas HTML y tres prefijos binarios de PDF. La validación incluye hora UTC,
URLs fuente, limitaciones, resultado del clasificador compartido y recuentos.
Se verificaron en vivo el anuncio MP18, la publicación MP20 y el catálogo
alojado en `estaticos.dipualba.es`: HTTP 200, `application/pdf` y firma `%PDF-`.
Se guardaron solo los primeros 4096 bytes de cada uno; no se afirma haber
validado el contenido completo de los 39 documentos ni su accesibilidad total.
El enlace BOP de MP16 se conserva con su esquema HTTP original y no se afirma
haber comprobado su descarga. No se accedió a bases de datos ni se publicó nada.
