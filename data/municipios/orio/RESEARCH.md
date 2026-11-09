# Orio — INE 20061, Gipuzkoa

Verificado mediante extracción HTTP real el 2026-11-09 con el Python preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y alcance

La sección oficial [Bulego teknikoa](https://orio.eus/udala/sailak/bulego-teknikoa/)
enlaza el [PGOU](https://orio.eus/hiri-antolamenduko-plan-orokorra/) y, desde la
navegación municipal, [Jendaurreko espedienteak](https://orio.eus/espedienteak/).
Este último es el inventario elegido: expedientes de exposición pública, con archivo,
textos explicativos, periodos y documentos agrupados en acordeones. Se extrae el
inventario completo, no una noticia escogida ni resultados de un buscador.

La cabecera HTML contiene `rel=next` hacia
https://orio.eus/espedienteak/page/2/, aunque no se ve paginación en el texto del
contenido. Se recorre esa segunda página, que repite los instrumentos y no tiene
siguiente. Se deduplican por ID municipal de artículo; discrepancias, ciclos,
continuaciones desconocidas o el límite de seguridad de 50 páginas causan error
sin reemplazar el JSONL. No se interpreta alcanzar ese límite como extracción completa.

Resultado real: **3 instrumentos, 57 enlaces documentales únicos dentro de cada
instrumento**:

- `17096`: HAPOko hiri-eremuen eta eremu urbanizagarrien etorkizuneko garapenen zonako plana.
  Plan zonal acústico que propone zonas de protección acústica especial; 1 PDF.
  Exposición: 2025-03-19 a 2025-05-06. No se infiere aprobación.
- `11571`: Hiri Antolamenduko Plan Orokorra 2023. PGOU, 52 documentos con memorias,
  normas, estudios, planos y presentación en euskera/castellano, agrupados en un
  registro. El relato municipal indica aprobación inicial por el pleno de
  **2022-12-22** (`fecha_acuerdo` y fase inicial). Exposición: 2023-01-19 a 2023-03-31.
- `9102`: HAPOaren aldaketa puntuala Dike-Kofradia eremu ez-jarraituan.
  Modificación puntual del PGOU, documento principal y tres anexos/estudios (4 enlaces).
  Exposición: 2021-03-23 a 2021-05-27. El inventario no proporciona acuerdo de aprobación.

El portal declara que no hay expedientes actualmente abiertos. Estos registros
proceden del archivo y no representan necesariamente el estado jurídico vigente.
No se usa la fecha inicial de exposición como fecha de publicación o acuerdo.
`fecha` y `fecha_publicacion` permanecen nulas; no se atribuye aprobación definitiva.
Cada documento conserva su título, URL de descarga y URL de procedencia con ancla.
No se extraen proyectos adicionales de los sectores o planos del PGOU.

## Exclusiones y límites

Se excluyen ordenanzas, reglamentos, formularios de licencia, licitación, servicios,
noticias y textos de navegación. El perfil del contratante no se convierte en
inventario de proyectos. No se ha verificado un registro de licencias concedidas;
`licencias.enabled=false` y los métodos de licencias devuelven vacío deshabilitado.
La cobertura se limita al inventario municipal anterior: no incluye todas las obras,
otras noticias ni la totalidad del registro provincial o de los boletines.
Los contenidos PDF se enlazan pero no se interpretan para extraer geometría,
fechas posteriores o estados jurídicos. Enlaces retenidos no equivalen a haber
verificado la descarga y el contenido de todos los documentos.

La web devolvió inicialmente HTTP 403 con el User-Agent predeterminado de requests;
con User-Agent compatible con navegador la consulta directa de las dos páginas fue
HTTP 200. El adaptador usa ese encabezado y falla ante errores HTTP o redirecciones
inesperadas. Las páginas de descubrimiento fueron contrastadas también en navegador.

## Geometría

`geometry_status: unavailable`. La navegación oficial ofrece
[Geo-Orio](https://www.geoorio.com/), pero no se ha verificado una capa vectorial
vinculada por ID a estos expedientes. Los planos son documentos, no geometrías
extraídas. No se asignan coordenadas ni centroides. `geocode.jitter_missing=false`;
los registros incluyen geometría nula y `publication_ready=false`.

## Validación y evidencias locales

Cinco pruebas con `python -m unittest municipio.test_orio -v`: agrupación documental,
exclusión de ordenanzas, fechas semánticas, instrumentos sin acuerdo, fallos ante
cambios de estructura/documentos, recorrido de paginación y deduplicación, métodos
de refresco y licencias deshabilitadas, y carga del manifest. Todas pasan.

Extracción real mediante `OrioAyuntamientoAdapter.backfill_proyectos`, con
`config={'capture_dir': 'evidence'}` y salida `evidence/proyectos.jsonl`:
3 registros. `evidence/validation.json` documenta recuento, URLs y limitaciones;
`evidence/inventory.html` y `evidence/page-2.html` conservan las respuestas del
recorrido real. Las capturas `probe-*.capture` conservan las respuestas 403 iniciales.
Evidencia local excluida del cambio de fuentes. Programación deshabilitada:
`schedule.enabled=false`. Sin cambios compartidos, dependencias, publicación o DB.
