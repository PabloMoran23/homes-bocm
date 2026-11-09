# Lezo — Gipuzkoa — INE 20053

Verificación en vivo: 2026-11-09. Fuente oficial municipal descubierta buscando
el inventario de planeamiento, no una noticia o anuncio de contratación:

- https://www.lezo.eus/es/plan-general-de-urbanismo
- Fuente operativa: https://azkena.lezo.eus/es/plan-general-de-urbanismo

Los dominios `www.lezo.eus` y `lezo.eus` fallan la validación de la cadena TLS
en este entorno, también con el almacén CA del sistema. El host municipal
`azkena.lezo.eus` sirve el libro del PGOU con HTTPS validado por requests, sin
anular la verificación. La selección de este host es explícita; el adaptador
no reintenta conexiones inseguras.

## Inventario y resultado

La portada enlaza cinco ramas: publicación BOG del PGOU, Memoria, Planos,
primera modificación AOU 6 Olatzar y segunda modificación AOU 31 Sagasti.
Memorias y planos pertenecen al PGOU; no son proyectos independientes.
Las siete subramas de Planos se recorren hasta sus documentos. Se usan los
mosaicos del contenido Drupal, excluyendo enlaces del menú global.

Extracción real mediante el adaptador cargado desde el manifest:
**3 instrumentos, 13 páginas HTML, 31 enlaces documentales**:

- Plan General de Urbanismo de Lezo: 28 documentos, incluyendo BOG,
  tres tomos de memoria y planos.
- Primera modificación del Plan General, AOU 6 Olatzar: un PDF «Anuncio GAO».
- Segunda modificación puntual del Plan General, AOU 31 Sagasti: dos PDFs,
  documento urbanístico y anuncio GAO.

Se conserva cada URL documental publicada y la página que la enlaza
(`documentos[].source_url`). Incluye URLs históricas `www.lezo.net`, sin
reescribirlas ni afirmar que todas estén disponibles. Se han descargado y
verificado como PDF los anuncios de Olatzar y Sagasti (HTTP 200); sus capturas
están en evidence/document3.pdf y evidence/document4.pdf.

## Fechas y semántica

`fecha_publicacion=2011-12-23` del PGOU procede del texto municipal que dice
expresamente «publicado en el Boletín Oficial de Gipuzkoa». No es una fecha de
aprobación. Los directorios de carga `2021-09` y `2022-10` no se usan como
fechas administrativas. `fecha`, `fecha_acuerdo` y `fecha_aprob` quedan nulas.
Las fechas de las modificaciones quedan nulas porque el adaptador no analiza
sus PDFs ni interpreta fechas dentro de nombres de archivo. La lectura auxiliar
del anuncio Sagasti confirma que es un instrumento urbanístico: publicación
BOG 14-07-2021 y acuerdo foral 22-06-2021 son eventos distintos, no incorporados
a los campos extraídos automáticamente. El PDF de Olatzar es escaneado y no
ofrece texto extraíble con pdftotext. No se atribuye una fase administrativa
solo a partir del título del inventario.

## Cobertura y geometría

Cobertura parcial: únicamente el árbol municipal del PGOU y las modificaciones
que enlaza actualmente. No garantiza todos los instrumentos aprobados, todas
las modificaciones vigentes ni las obras públicas del municipio. No se incluyen
formularios, licitaciones ni noticias ajenas como proyectos o licencias.
No se ha verificado un registro público de licencias concedidas: deshabilitadas.

No hay paginación en las 13 páginas observadas. Se recorren todas las ramas,
sin límite de resultados que trunque la salida. El adaptador falla ante paginación,
ramas principales nuevas sin clasificar, hojas sin documentos, pérdida del marcado
o un árbol que supere el límite de revisión de 150 páginas. La escritura final es
atómica; un error conserva la extracción anterior. Las actualizaciones refrescan
la instantánea entera y no implican bajas legales de instrumentos.

geometry_status: unavailable. Los planos son documentos PDF; no se ha verificado
geometría vectorial asociada por identificador. Coordenadas y geometría nulas,
`publication_ready=false`, `geocode.jitter_missing=false`, `schedule.enabled=false`.

## Reproducción y evidencias locales

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Pruebas: `-m unittest municipio.test_lezo -v` (3 aprobadas). Comprueban agrupación
recursiva y deduplicación documental, fechas separadas, rechazo de paginación,
contenido inválido y conservación de la salida anterior tras fallo; además de
carga del manifest y licencias deshabilitadas.

La ejecución real carga `load_manifest('lezo')` y `load_portal_adapter`, configura
`capture_dir='evidence/captures'` y llama únicamente a
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`. No usa el orquestador.
`evidence/validation.json` contiene conteo, URLs visitadas y limitaciones;
`evidence/captures/` contiene las 13 respuestas HTML. Evidencias locales,
no destinadas al commit. No se usan DB, publicación ni servicios de despliegue.
