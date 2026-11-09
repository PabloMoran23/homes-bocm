# Lazkao — INE 20049, Gipuzkoa

Verificación directa: 2026-11-09. Un único adaptador municipal, con cobertura
parcial de dos instrumentos de planeamiento; no es un censo de obras ni licencias.

## Descubrimiento y fuentes

La navegación oficial de [Urbanismo y Medio Ambiente](https://www.lazkao.eus/es/ayuntamiento/servicios/urbanismo-y-medio-ambiente.html)
contiene principalmente trámites de solicitud. «Obras mayores», «Obras menores» y
las solicitudes de licencia no acreditan concesiones y quedan fuera de la extracción.
No se usa contratación pública como prueba de proyecto aprobado.

1. [Normas subsidiarias](https://www.lazkao.eus/es/ayuntamiento/normas-subsidiarias.html):
   la página municipal incorpora explícitamente el iframe
   [inventario/visor de NNSS](https://herrigis.gis-cdn.net/lazkao_aass/index_es.html).
   La sección `#deskarga` ofrece **11 documentos** (memoria, normas generales y
   planos). El dominio externo es una fuente delegada por enlace municipal,
   no una fuente supuesta a partir del nombre del municipio. Se comprueba el
   enlace iframe en cada ejecución y se conserva esa cadena de procedencia.
2. [Inicio PGOU](https://www.lazkao.eus/es/pgou/inicio-pgou.html): identifica el nuevo
   Plan General de Ordenación Urbana de Lazkao y enlaza
   [Diagnóstico PGOU](https://www.lazkao.eus/es/pgou/diagnostico-pgou.html).
   Este catálogo Phoca Download expone **28 documentos**, incluido el diagnóstico
   y planos/anexos territoriales PTP/PTS. Esos anexos de contexto se conservan como
   documentos del inventario de diagnóstico, no como otros 27 proyectos.

Resultado vivo: **2 registros**, NNSS y nuevo PGOU, con **39 documentos enlazados**.
Los identificadores son estables por instrumento, independientes del orden de los
anexos. Cada documento conserva su título, URL y página de procedencia. Se codifican
los espacios de las URLs del visor. No se crean registros por PDF ni por noticia.

## Fechas, estado y límites

No se asignan fechas de publicación, acuerdo o aprobación a ninguno de los dos
instrumentos: se mantienen explícitamente nulas. Los metadatos emergentes del
catálogo de diagnóstico indican «06 Noviembre 2025» como fecha de archivo; eso no
prueba la fecha de aprobación ni la publicación del plan. La página de inicio PGOU
lista fases futuras, incluida aprobación definitiva: el parser no convierte esa
lista en estado real del expediente. Tampoco se afirma que la colección NNSS sea
un texto consolidado que incorpore todas las modificaciones posteriores.

Las dos colecciones revisadas son páginas completas, sin enlaces activos de
paginación (Phoca muestra un contenedor de paginación vacío). Se leen todos los
bloques documentales. Si aparecen enlaces de paginación/continuación el adaptador
falla expresamente, sin escribir un resultado parcial; habrá que ampliar el recorrido.
La actualización relee ambas colecciones completas, sin cortes temporales. Si falta
la identidad, procedencia o documentación principal, falla conservando el JSONL previo.

El HTML municipal contiene enlaces ajenos al urbanismo fuera del contenido útil.
Se ignoran: la extracción está acotada al artículo del plan y a los contenedores
oficiales de documentos. No se siguen instrucciones ni enlaces arbitrarios del HTML.

No se cubren el histórico del boletín provincial, actas, modificaciones no presentes
en estos inventarios, noticias de obras, concesiones de licencias ni todo el universo
de documentos municipales. Licencias y programación automática deshabilitadas.

## Cartografía

`geometry_status: unavailable` para estos dos registros. El visor municipal usa
Leaflet y enlaza `https://herrigis.gis-cdn.net/lazkao_aass/aiu.js`, con áreas AIU.
No se confunden esos ámbitos con la geometría completa de las NNSS o del PGOU;
no se asignan centroides, coordenadas del ayuntamiento ni geometrías inferidas.
La captura local permite revisar esa limitación. `geocode.jitter_missing: false` y
`publication_ready: false` en los registros.

## Validación reproducible y evidencia local

Runtime empleado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_lazkao -v` — **6 pruebas pasan**:
agrupación y deduplicación documental, procedencia, URLs, fechas/estado no inferidos,
rechazo de páginas incompletas y paginación, actualización atómica, licencias
deshabilitadas y carga del manifiesto. Los fixtures son sintéticos; las capturas y
registros reales son evidencia separada.

Extracción real ejecutada mediante
`LazkaoAyuntamientoAdapter('lazkao', config={'evidence_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.

En `evidence/` (local, no destinado a commit): `proyectos.jsonl`, `validation.json`,
las cuatro páginas fuente HTML, captura de la navegación de Urbanismo, `aiu.js` y
el PDF principal de NNSS y los bytes originales de la respuesta PDF del diagnóstico. La validación
registra conteos, URLs, límites, hora UTC y hashes de los PDF comprobados. Se retienen
los enlaces a los demás anexos; no se afirma haber descargado o validado su contenido.
La respuesta `application/pdf` del diagnóstico contiene 560 bytes de texto HTML ajeno
antes de `%PDF-`; se conserva íntegra como `.response.bin`. `pdftotext -f 1 -l 2`
puede leerla y confirma «HAPO LAZKAO / DIAGNÓSTICO», «LAZKAO (GIPUZKOA)»,
promotor «LAZKAOKO UDALA» y fecha documental «09.2025». Esta última tampoco se
convierte en fecha de aprobación. La integridad del sitio no está certificada;
la anomalía queda explícita en `validation.json`. No se ejecutó publicación,
base de datos ni ningún paso global del pipeline.
