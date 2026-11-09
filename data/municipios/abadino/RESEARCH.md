# Abadiño — INE 48001, Bizkaia

Revisión: 2026-11-08. Adaptador municipal independiente; sin cambios compartidos.

## Descubrimiento y fuentes oficiales

El dominio municipal confirmado por el directorio de Bizkaia es
https://www.xn--abadio-0wa.org/ (abadiño.org, no abadino.eus).
La portada española y el JavaScript público `iturrigorri.js` exponen el menú
mediante SharePoint REST. Su lista pública `Menu Segundo Nivel` enlaza Urbanismo:
https://www.xn--abadio-0wa.org/es-ES/Servicios/Urbanismo/Paginas/default.aspx

El inventario público de páginas de esa área se consulta mediante GET anónimo:
https://www.xn--abadio-0wa.org/es-ES/Servicios/Urbanismo/_api/web/lists/getbytitle('Páginas')/items?$select=Id,Title,File/ServerRelativeUrl&$expand=File&$top=100

Se seleccionan exclusivamente las columnas de título, identificador y ruta de
página. No se consultan formularios ni listas de solicitudes en el adaptador.
La consulta revisada contiene 64 páginas y no devuelve continuación, pero el
adaptador sigue `d.__next` hasta agotarla, rechazando ciclos y destinos ajenos.

El catálogo oficial foral
https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-abadino
ofrece datos globales hasta 2026, pero sus agregados de suelo/viviendas no son
expedientes individuales y se excluyen. Tampoco se convierten licitaciones,
formularios o noticias en proyectos o licencias concedidas.

## Cobertura y agrupación

Se descubren en el inventario municipal estas cuatro cabeceras de instrumentos:

- Plan General de Ordenación Urbana: `PlanGeneraldeOrdenacionUrbana.aspx`.
- MPNS I-12 I-13 I-14: `MPNSI-12I-13I-14.aspx`.
- Modif NNSS Murueta: `ModifNNSSMurueta.aspx`.
- Aprobación Provisional NNSS SG Sanitario asistencial e-17:
  `aprobacion-provisional-nnss-sg-sanitario-asistencial-e17.aspx`.

Todas bajo `/es-ES/Servicios/Urbanismo/Paginas/` del dominio municipal.
El PGOU reúne preavance, avance, documentación ambiental, aprobación inicial y
segunda aprobación inicial en **un instrumento**, siguiendo los enlaces de sus
páginas y anexos. Las modificaciones se mantienen como instrumentos distintos.
Cada documento PDF conserva URL, título y páginas de procedencia; se deduplica
por URL. Los IDs dependen de la URL de cabecera, no del orden ni del número de
anexos. Se conservan también los documentos de fases anteriores publicados.

Hay paginación HTML numérica en anexos del PGOU (hasta `?page=5`); se siguen
estos enlaces y se deduplican las visitas. Las páginas de anexos deben figurar en
el inventario (comparación por ruta, conservando la consulta para recorrer todas
las páginas). Una paginación «Siguiente» no reconocida provoca un error explícito.
Los límites defensivos provocan error y no escritura de resultados parciales.

Cobertura **parcial**, limitada a cabeceras PGOU/MPNS/Modif NNSS/Aprobación
Provisional NNSS. No es el inventario total de proyectos, obras públicas o
instrumentos urbanísticos de Abadiño. Por ejemplo, TAV, estudios de movilidad e
inventario de caminos quedan fuera del alcance implementado.

## Semántica, fechas y localización

Las fases proceden de los rótulos de páginas y documentos. No prueban vigencia
ni aprobación definitiva actual: el portal conserva material histórico. Si no
se identifica una fase en esos rótulos se deja nula. No se interpretan fechas de
nombres de archivo, metadatos de carga o fecha de consulta como fechas de
acuerdo, aprobación o publicación. `fecha`, `fecha_publicacion`, `fecha_acuerdo`
y `fecha_aprob` quedan nulas; el adaptador no interpreta el texto interior de PDFs.

`geometry_status: unavailable`. Los planos enlazados son PDFs; no se ha
verificado una geometría vectorial vinculada a estos instrumentos. No se
inventan coordenadas, centroides, CRS ni fechas. `publication_ready: false`.
`schedule.enabled: false`, `licencias.enabled: false` y
`geocode.jitter_missing: false`.

## Validación reproducible y evidencia local

Runtime autorizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_abadino -v` (4 pruebas): agrupación
multidocumento y fases, anexos numerados, deduplicación y procedencia,
continuaciones OData y ciclos, fallos de estructura y documentos ausentes,
exclusión de enlaces ajenos, manifiesto y licencias deshabilitadas.

Extracción: instanciar `AbadinoAyuntamientoAdapter(config={'capture_dir':
'evidence/live'})` y llamar `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
El resultado real, número de registros, URLs visitadas y limitaciones se guardan
en `evidence/validation.json`; las respuestas originales están en
`evidence/live/`. La ejecución real produjo **4 instrumentos y 356 enlaces PDF**
(23 del MPNS industrial, 11 de Murueta, 319 del PGOU y 3 del E-17), tras
66 peticiones de inventario/páginas. Se descargó y verificó la cabecera PDF de
un documento representativo por instrumento (HTTP 200 en los cuatro), guardando
los archivos completos y sus hashes SHA-256 en la evidencia. El PGOU se reunió
a partir de 63 URLs de páginas, incluyendo consultas de paginación.
`evidence/tests.txt` conserva el resultado de las cuatro pruebas. Evidencia local no destinada a commit. No se han instalado
dependencias ni usado servicios de publicación, bases de datos o despliegue.
