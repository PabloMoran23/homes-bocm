# Carbajosa de la Sagrada — Salamanca — INE 37085

Consulta y extracción real: 8 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuente oficial e inventario

https://carbajosadelasagrada.es/urbanismo/

La página del Ayuntamiento publica un inventario estático de planeamiento y gestión
urbanística, con documentos municipales y enlaces a Google Drive publicados por el
propio Ayuntamiento. No es un listado de noticias ni de licitaciones. El pie identifica
Ayuntamiento de Carbajosa de la Sagrada, Salamanca, CIF P3708500H.
Se revisaron el contrato `municipio/adapters/portal.py`, el cargador de manifests,
el registro y los ejemplos de Chipiona y Manlleu antes de implementar.

La extracción devuelve **13 instrumentos, con 34 enlaces documentales**:
PGOU (cinco tomos); modificación puntual Apéndice I-4; modificación nº 3 del Plan
Parcial R10 El Canal; PERI SUNC R-1 Camino de Santa Marta; Plan Parcial SUR-I-1;
proyecto de actuación UA nº 1 SUNC-R1; modificación puntual nº 1 del PGOU;
estudios de detalle de Avda. Carbajosa 13 y C/ Newton 15; normalización AAUN-16;
actuación V03 SUR I-1; modificación del PERI SUNC-R-1; normalización SUR-AE-PAS-1
Los Paúles. Se mantienen separados planes y proyectos de actuación de un mismo
sector, porque son instrumentos distintos.

Los tomos, partes, fichas, planos y anuncios iniciales/definitivos de cada instrumento
se agrupan en un registro. Cada enlace conserva título, URL original, contexto y
página de procedencia. Se ignoran enlaces gráficos repetidos a un archivo de Drive.
Se excluye el convenio de gestión AANU-16, sin confundirlo con el proyecto de
normalización. No se extraen formularios como licencias ni se usan anuncios de
contratación como proyectos.

No hay paginación observada en este inventario: todos los documentos están en el
HTML. El parser procesa el contenedor completo y rechaza indicadores de paginación
si aparecen, evitando una extracción truncada. La falta de encabezado o de enlaces
para un instrumento provoca error. Actualizar vuelve a obtener la instantánea completa.

## Semántica y límites

Cobertura parcial: inventario disponible en la fecha de consulta; no constituye
histórico exhaustivo, catálogo de toda la obra pública ni garantía de vigencia o
última fase de cada instrumento. Se mantienen las afirmaciones municipales en
`source_statements`. `fase` refleja únicamente la fase expresamente publicada.
`fecha_publicacion` corresponde a la última publicación BOCyL indicada para el
instrumento; los contextos documentales conservan las publicaciones anteriores.
`fecha_aprob` y `fecha_acuerdo` se rellenan únicamente con fechas numéricas
explícitas de aprobación/acuerdo; no se convierten publicaciones en acuerdos.
La fecha textual de la orden del PGOU se conserva literalmente, sin normalizarla.
Los Paúles no tiene fecha explícita en la página y se deja nula.

Los registros son conjuntos documentales (`source_entity_type: documento`), sin
números de expediente inventados ni afirmación de actividad elegible. La política
compartida los reconoce como documentos. No hay geometría verificada: coordenadas
nulas y `publication_ready: false`. Manifest con `schedule.enabled: false`,
`geocode.jitter_missing: false` y `licencias.enabled: false`. No se ha verificado
un registro público de licencias concedidas.

Los enlaces documentales se conservan tal como los publica el Ayuntamiento,
incluidos HTTP. No se ha validado individualmente cada documento ni leído el
contenido completo de PDFs o archivos de Drive. La muestra de la modificación
R10 se consultó por HTTPS: HTTP 200, `application/pdf`, firma `%PDF-` en los
primeros 4096 bytes. Esto valida esa muestra, no todos los enlaces.

## Validación reproducible y evidencia local

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_carbajosa_de_la_sagrada -v`

Cuatro pruebas: agrupación y aislamiento documental, fechas de publicación/acuerdo,
rechazo de contenido vacío/redirecciones documentales externas/paginación,
y contrato de backfill/update y resolución del manifest.

Se ejecutó realmente `load_portal_adapter(load_manifest(...)).backfill_proyectos(...)`,
con captura habilitada mediante `capture_dir` solo en la ejecución local. Resultado:
13 registros y política de entidades con `status: ok`, cero identidades desconocidas.
Evidencia local no destinada a commit:
`evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/urbanismo.html`,
`evidence/document_sample.bin`, `evidence/proyectos.entities.json` y
`evidence/parser-tests.txt`. `validation.json` incluye hora UTC, fuente, cobertura,
limitaciones y respuesta de la muestra PDF. Sin bases de datos ni publicación.
