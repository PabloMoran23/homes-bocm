# Muros — INE 15053, A Coruña

Verificación: 2026-11-08. Cobertura parcial de instrumentos de planeamiento;
no es un inventario de obras recientes ni de licencias concedidas.

## Descubrimiento y fuentes oficiales

La página del Concello https://muros.gal/urbanismo/ contiene el enlace
«PLAN XERAL DE ORDENACIÓN MUNICIPAL (PXOM) + PLAN ESPECIAL» a
https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15053.
La página actual de SIOTUGA también responde en
https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=15053.
La selección pública identifica expresamente `15053` como Muros, distinto de Muras.
Los formularios y trámites de Urbanismo no se interpretan como concesiones.

El inventario carga sus registros mediante JavaScript oficial:
https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js?2.5.0.
Se reprodujeron las consultas públicas del formulario, sin autenticación:

- POST `assets/inventario/query_document.php`: `id=15053`, `idclase=14`
  (planeamiento general), `13` (desarrollo), `18` (delimitaciones rurales).
- POST `assets/inventario/getIOTPU.php`: `iddoc`, `idp=0`, `lang=gl_ES`.
- El nonce del formulario se obtiene de la página pública en cada ejecución;
  no es una credencial ni se incorpora a los registros.

Cada consulta devuelve un array completo o `null` para ausencia. La paginación
DataTables se realiza en cliente sobre ese array: no hay parámetro de página,
límite ni recorte en el adaptador. Una respuesta con envoltorio/paginación en vez
de array provoca error. Se recorren todos los elementos y componentes de detalle.
La clase histórica `16` se consultó durante la investigación y devolvió `null`;
no forma parte de la actualización del inventario actual. Los instrumentos de
ordenación territorial, consultados por otra sección del portal, quedan fuera.

## Resultado real y semántica

Dos instrumentos, agrupados por identificador SIOTUGA:

| ID | Instrumento | Aprobación definitiva | BOP | DOG | Documentos únicos |
| --- | --- | --- | --- | --- | --- |
| 22396 | PLAN XERAL DE ORDENACIÓN MUNICIPAL | 2010-12-10 | 2010-12-24 | 2010-12-24 | 529 |
| 23632 | PROTECCION DO CONXUNTO HISTORICO-ARTISTICO (Plan Especial) | 2008-05-09 | 2008-06-09 | 2008-06-24 | 216 |

El PXOM contiene 535 referencias de componentes, seis repetidas por URL;
se conservan 529 documentos únicos y todos sus grupos de procedencia. El Plan
Especial contiene 216. No se generan proyectos separados por plano, memoria o
normativa. Se retienen títulos, IDs y enlaces PDF/JPG construidos exactamente
como hace el JavaScript con `filesroot`, `folder` y `pathesperado`.

`fechaaddef` se guarda como `fecha_aprob`; no se atribuye a un acuerdo municipal.
`fechabop`, `fechadog` y `fechanormativabop` se guardan en campos específicos,
sin elegir arbitrariamente una fecha de publicación genérica. `fecha`,
`fecha_acuerdo` y `fecha_publicacion` quedan nulas. Se conservan incidencias
jurídicas y fecha de texto refundido si el inventario los publica. El detalle debe
coincidir con el ID, municipio y fechas de la lista; cualquier discrepancia falla.
No se afirma que estos instrumentos antiguos sean aprobaciones recientes.

## Geometría y limitaciones

geometry_status: unavailable

SIOTUGA ofrece un visor cartográfico y servicios WMS en su sección Urbanismo.
Esta extracción usa el inventario documental; no se verificó una geometría
vectorial por instrumento. Los JPG/PDF de planos permanecen enlazados, sin
vectorización, centroides ni coordenadas inventadas. `publication_ready=false`.
La existencia del instrumento en el inventario no equivale a licencia concedida.
No se extrajeron licencias, contratación, anuncios de licitación ni noticias.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Pruebas: `python -m unittest municipio.test_muros -v` — 4 correctas.
Cubren agrupación de documentos, fechas independientes, duplicados conflictivos,
rechazo de envoltorios de paginación, procedencia, ausencia de documentos,
resolución del manifest y licencias deshabilitadas.

Se ejecutó `load_portal_adapter(load_manifest('muros')).backfill_proyectos(...)`
con captura local habilitada mediante `config.capture_dir`. Resultado: 2 registros,
745 documentos únicos. La política compartida clasificó ambos como `unknown`;
se conserva su resultado sin alterar reglas comunes. No impide verificar que son
instrumentos de planeamiento, pero no se afirma que estén listos para publicar.
`update_proyectos` vuelve a extraer la instantánea completa, sin seguimiento de
bajas históricas. Las licencias devuelven un fichero vacío con estado disabled.

Evidencias locales en `evidence/`: `proyectos.jsonl`, `validation.json`, HTML
municipal e inventario, JavaScript de consultas y respuestas JSON completas por
clase/detalle. Se descargó y verificó HTTP 200/application-pdf para
https://siotuga.xunta.gal/siotuga/documentos/urbanismo/MUROS/documents/23632me100.pdf
(`23632me100.pdf`); no se descargaron ni comprobaron uno a uno los 745 enlaces.
Las evidencias no forman parte de los cuatro archivos fuente entregados.
Programación y licencias deshabilitadas; `geocode.jitter_missing=false`.
