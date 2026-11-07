# Solsona — INE 25207, Lleida, Catalunya

Verificación en vivo: 2026-11-07. Adaptador de un inventario municipal de proyectos
físicos en exposición pública. Cobertura parcial; no es un registro histórico de
obras ni de licencias concedidas.

## Fuentes oficiales descubiertas

- Área de Urbanismo: https://www.ajsolsona.cat/arees/urbanisme
  Distingue solicitudes de licencia, planeamiento y licitaciones. Los formularios
  de solicitud no acreditan concesiones y no se extraen.
- Planeamiento: https://www.ajsolsona.cat/arees/urbanisme/poum
  Inventario accesible con POUM, gestión del suelo, convenios, catálogos, plan
  parcial Cabana del Silo y enlace MUC. Se capturó para investigación, pero no
  forma parte de la extracción de este adaptador. No se presenta como cobertura
  íntegra del planeamiento ni del RPUC.
- Inventario utilizado: https://www.ajsolsona.cat/ajuntament/projectes-en-exposicio-publica
  Accesible anónimamente, HTML Plone con artículos `tileItem`. La consulta real
  contiene **un proyecto**, aunque el índice del buscador todavía muestra otros
  proyectos de urbanización. El adaptador usa exclusivamente el inventario vivo.

## Registro y documentos

Proyecto de rehabilitación de las pistas deportivas 2 y 3 del carrer del Pedraforca:

https://www.ajsolsona.cat/ajuntament/projectes-en-exposicio-publica/projecte-de-rehabilitacio-de-les-pistes-esportives-2-i-3-del-carrer-del-pedraforca/view

Documento técnico enlazado por la propia ficha:

https://www.ajsolsona.cat/ajuntament/projectes-en-exposicio-publica/projecte-de-rehabilitacio-de-les-pistes-esportives-2-i-3-del-carrer-del-pedraforca/at_download/file

Se descargó el PDF real (5.649.698 bytes, HTTP 200, `application/pdf`) y se
inspeccionó su texto con `pdftotext`. Contiene memoria descriptiva y constructiva,
presupuesto y documentación gráfica. Identifica la reforma de las pistas 2 y 3,
promotor Ajuntament de Solsona, emplazamiento Carrer Pedraforca 10 y expediente
2310/2026. Estos datos confirman que es un proyecto físico, no un anuncio de
contratación. El adaptador extrae el título y los enlaces de HTML; no interpreta
automáticamente el PDF ni transforma su índice en registros independientes.

Una ficha genera un registro; sus documentos se agrupan en `documentos`, con
URL y `source_url` de procedencia. Identidad estable por URL municipal canónica
sin `/view`. El enlace de descarga original se conserva íntegro.

## Semántica y límites

La ficha no muestra fechas explícitas de publicación, acuerdo o aprobación;
todos esos campos y la fecha genérica permanecen nulos. El año del expediente,
metadatos HTTP y fechas de documentos no se convierten en fechas de aprobación.
La fase «exposición pública» proviene del contexto del inventario, sin afirmar
que las obras estén aprobadas, adjudicadas, iniciadas o terminadas.

Solo se aceptan títulos de proyectos de obra física reconocibles. Se excluyen
trámites, licitaciones, noticias y documentos ajenos a ese alcance. No hay
paginación en la captura actual; el adaptador recorre enlaces de paginación
Plone, páginas numeradas y `rel=next`, deduplicando registros. Si supera 100
páginas o pierde contenido/fichas/documentos, falla sin sustituir la salida
anterior: nunca entrega silenciosamente las primeras páginas.

No hay geometría verificada vinculada al proyecto. No se geocodifica el domicilio
municipal ni se convierten planos PDF en coordenadas. Latitud, longitud y geometría
son nulas, `publication_ready=false`, `geocode.jitter_missing=false`.
Licencias deshabilitadas y salida vacía explícita; programación deshabilitada.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Pruebas: `-m unittest municipio.test_solsona -v`.
Cubren selección de obras, deduplicación, agrupación documental, fechas nulas,
paginación con dos páginas, rechazo de HTML inesperado y conservación de la
instantánea previa ante fallo, además del manifest y licencias deshabilitadas.

Extracción real mediante `backfill_proyectos` del adaptador cargado desde el
manifest. Evidencias locales en `evidence/proyectos.jsonl`, `validation.json`,
HTML de inventarios y ficha, PDF y texto de inspección. No forman parte de los
cuatro archivos fuente. La validación detalla recuento, fuentes y limitaciones.
