# Magán (Toledo), INE 45088

Revisión en vivo: 2026-11-09. Adaptador para un instrumento real de planeamiento
municipal, con cobertura parcial. No es un inventario de licencias concedidas.
Programación automática, geocodificación con jitter y licencias desactivadas.

## Fuentes oficiales e inventarios comprobados

- https://magan.es/ identifica el Ayuntamiento y enlaza su sede electrónica.
- https://magan.sedelectronica.es/transparency/ devuelve HTTP 200 y muestra
  «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE (0)». No se convierte una
  categoría vacía en registros. No se ha acreditado un registro público de
  licencias concedidas.
- https://magan.es/tramites/ publica solicitudes (obra mayor, menor, primera
  ocupación), no concesiones. Excluidas.
- https://magan.es/noticias-y-anuncios/ contiene en su listado actual numerosas
  entradas ajenas al municipio (torrents y software). No se usa como inventario
  de proyectos. No se ejecutaron scripts de esa página ni se siguieron sus
  enlaces ajenos al Ayuntamiento. El archivo municipal de plenos
  https://magan.es/plenos/ muestra actas antiguas; no se ha hecho extracción
  exhaustiva de acuerdos históricos.
- https://urbanismo.castillalamancha.es/planeamiento/planeamiento-municipal/instrumento-planeamiento-municipal
  explica el depósito oficial y sus límites: documentación disponible en la
  Consejería, posible falta de remisiones o refundidos, carácter informativo,
  sin sustituir expedientes ni ejemplares diligenciados.
- Inventario estructurado oficial:
  https://geoservicios.castillalamancha.es/arcgis/rest/services/Vector/Planeamiento_Municipal/MapServer/0
  Campos comprobados: COD_INE, COD_PROV, MUNICIPIO, PLAN_, NOM_PLAN,
  FECHA_APRO, FECHA_ACTU, DESCARGA. Consulta exacta COD_INE='45088': un
  registro, COD_PROV='45', MUNICIPIO='Magán', NNSS-B, disponible SI.
- Documento oficial enlazado por ese registro:
  https://ficheroscomunes.castillalamancha.es/planeamiento/TOLEDO/45088_MAGAN.zip
  HTTP 200, 31.747.814 bytes en la comprobación. Contiene 19 PDF: memoria,
  normativa, planos y documentos de modificaciones. Los nombres originales,
  incluyendo caracteres mal codificados por el archivo, se conservan literalmente.

## Cobertura, semántica y agrupación

Un único registro: **Normas Subsidiarias tipo b de Magán**. FECHA_APRO del
catálogo equivale a 1993-02-09; se guarda en fecha_aprob como fecha declarada
por el inventario, sin afirmar que se haya verificado el acuerdo original.
FECHA_ACTU equivale a 2019-05-15 y se guarda exclusivamente como actualización
del catálogo. fecha_publicacion, fecha_acuerdo y fecha genérica son null.
No se deducen fechas de las carpetas, los nombres de los PDF o el día de descarga.
La fase queda null: no se atribuye un nuevo acuerdo a los documentos agrupados.

Todos los PDF se retienen en documentos del instrumento padre con el enlace de
su contenedor ZIP y archivo_interno. No se inventan enlaces de descarga individual
ni se crean proyectos separados para cada plano o texto. Las modificaciones
incluidas no tienen sus propias fechas de aprobación verificadas ni se presentan
como inventario exhaustivo de instrumentos posteriores. El adaptador registra
los atributos originales y el SHA-256 del contenedor para trazabilidad.

No cubre todas las obras públicas, PAU, modificaciones posteriores, contratación
ni acuerdos municipales. El endpoint cartográfico contiene polígonos de inventario
municipal; no se usan como geometría del instrumento o de actuaciones. lat, lon y
geometry permanecen null y publication_ready=false.

## Operación y validación reproducible

Runtime: /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python

Pruebas: `python -m unittest municipio.test_magan -v` (6 casos). Verifican
identidad municipal/provincial, fechas distintas y ausentes, rechazo de inventarios
incompletos o truncados, agrupación de documentos, rechazo de ZIP inválido/vacío,
conservación del resultado previo ante fallos y licencias desactivadas.

Extracción real ejecutada con load_manifest('magan'), load_portal_adapter y
backfill_proyectos hacia evidence/proyectos.jsonl. Consulta de recuento independiente
más consulta completa, ambas filtradas por INE. Se exige concordancia y un único
instrumento: si crece el inventario o exceededTransferLimit es true, falla
explícitamente para revisar el parser, sin truncar ni aceptar cobertura oculta.
Actualizaciones refrescan la instantánea completa; no se usa una fecha de corte.

Descargas con timeout, tamaño acotado (2 MB JSON, 80 MB ZIP); errores HTTP,
cambios de identidad o de ubicación documental y cambios incompatibles del
archivo impiden escribir un resultado parcial. Escritura final mediante reemplazo
atómico. No se extrae el ZIP al sistema de archivos.

Evidencias locales no destinadas a commit: evidence/proyectos.jsonl,
evidence/validation.json, evidence/live/{count.json,inventory.json,archive.zip},
capturas HTML de los índices consultados y listado del ZIP. La validación contiene
el recuento real, URLs y limitaciones. No se han modificado fuentes compartidas ni
dependencias, ni usado publicación, credenciales o servicios de producción.
