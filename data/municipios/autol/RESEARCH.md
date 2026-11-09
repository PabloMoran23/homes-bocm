# Autol — La Rioja — INE 26021

Verificación y extracción real: 2026-11-09. Adaptador:
`municipio.adapters.autol:AutolAyuntamientoAdapter`.

## Descubrimiento y fuente oficial

La navegación municipal Ayuntamiento → Urbanismo conduce al inventario:
https://aytoautol.larioja.org/ayuntamiento/urbanismo

Se consultaron antes los ejemplos Hernani y Chipiona, `municipio/manifest.py`,
`municipio/adapters/portal.py` y el registro de adaptadores. El manifiesto utiliza
el mismo contrato e identifica Autol, provincia y comunidad autónoma La Rioja,
código INE 26021. Se carga por ruta explícita, sin modificar código compartido.

La búsqueda encontró también la versión con `www`, que falla en requests por
incompatibilidad del nombre del certificado. La versión sin `www` sirve HTTP 200
con verificación TLS normal. No se desactiva la verificación. Los enlaces a
archivos locales se normalizan al dominio sin `www`, conservando ruta y query.

Otros inventarios/áreas oficiales identificados en la navegación y búsqueda:

- https://aytoautol.larioja.org/ayuntamiento/proyecto-instalaciones/pasarela-rio-cidacos
- https://aytoautol.larioja.org/ayuntamiento/proyecto-instalaciones/auditorio-municipal
- https://aytoautol.larioja.org/ayuntamiento/plenos
- https://autol.sedelectronica.es/info.0 y su tablón `/board`.

Son candidatos para ampliar cobertura, no fuentes recorridas por este adaptador.
El catálogo de solicitudes de licencia no demuestra licencias concedidas. Los
anuncios de contratación tampoco se convierten en proyectos. No se recoge la
página de categoría `/ayuntamiento?start=20`, que mezcla artículos y paginación.
Se recoge el artículo completo de Urbanismo, sin paginación en la captura real.

## Cobertura comprobada

Una fila por instrumento/proyecto, con documentos agrupados:

| Instrumento | Enlaces | Publicación BOR indicada en web |
| --- | ---: | --- |
| Reurbanización de calle Carasol | 1 | No indicada |
| Modificación del Plan Parcial sector S-2, zona industrial | 3 | 2018-11-09 |
| Plan General Municipal de Autol | 16 | No indicada |
| Modificación puntual nº 22 | 6 | No indicada |
| Modificación puntual nº 24 | 2 | 2017-09-08 |
| Modificación puntual nº 25 | 6 | 2018-03-09 |
| Modificación puntual nº 26, carretera Calahorra 8 | 4 | 2020-09-16 |
| Plan Parcial S-5 | 28 | 2021-02-15 |
| Modificación puntual nº 27, UE-29 | 2 | 2024-12-30 |

Total real: **9 registros, 68 enlaces documentales**. Incluye PDF, DWG y enlaces
al visor del BOR; un documento repetido en una sección se conserva una sola vez.
Los documentos se asignan por cabeceras h1 dentro del cuerpo del artículo,
incluso cuando la modificación nº 27 está anidada en el mismo div que S-5.
Las cabeceras h2 de planos, fechas o plazos no crean instrumentos adicionales.
La memoria, normativa, planos, informes y anuncio siguen dentro del mismo registro.
El identificador deriva del título normalizado del instrumento.

`descripcion` conserva el texto publicado de cada sección. Cada documento retiene
su título, URL y `source_url` del inventario. No se interpretan como proyectos los
formularios, el horario del arquitecto, menús, publicidad ni noticias ajenas.

## Fechas y estado

`fecha_publicacion` significa publicación en BOR según la expresión explícita del
inventario, con `fecha_publicacion_fuente`. No se usa la fecha del copyright,
la recuperación HTTP, el nombre de archivo, un plazo de alegaciones ni la fecha
alternativa de un periódico como fecha del acuerdo.

Sólo la modificación nº 24 proporciona en el HTML un acuerdo inicial explícito:
`fecha_acuerdo=2017-09-04`, separado de `fecha_publicacion=2017-09-08`. Su fase
es un hito histórico según el texto, no una confirmación del estado actual.
No se atribuye aprobación al resto por la mera existencia de documentos.

Como comprobación documental adicional se descargó el PDF BOR enlazado para nº 27:
https://aytoautol.larioja.org/images/URBANISMO/BOR%2030-12-2024%20modificiacion%20n.27%20ue%20-29.pdf
HTTP 200, 237970 bytes, cabecera PDF válida. La lectura local mediante pdftotext
confirma publicación de aprobación definitiva de la modificación nº 27 en BOR
255 de 30-12-2024 y acuerdo de 13-12-2024. El extractor de inventario no analiza
PDFs y **no incorpora esa fecha de acuerdo** a los registros. Captura y texto
quedan en evidence para revisión. No se comprueban todas las descargas.

## Límites y comportamiento

Cobertura parcial del inventario documental publicado hoy, con materiales
históricos; no implica que sean todos los instrumentos vigentes ni todas las
obras. No se recorren sede, histórico de actas, BOR completo ni las dos páginas
separadas de proyectos de instalaciones. Sin geometría vinculada por expediente:
`geometry_status=unavailable`, `publication_ready=false`. No se inventan puntos,
CRS o coordenadas y no se vectorizan planos DWG/PDF. La política compartida
anotó 9 entidades como categoría desconocida; no se modifica esa política.

El extractor falla ante cuerpo ausente, ausencia de instrumentos, instrumento
sin documentos, cabeceras duplicadas, redirección inesperada o indicadores de
paginación (`rel=next`, pagination, pagenav, article-index). Si aparece paginación,
es necesario ampliar el recorrido; no se acepta truncar. Actualizar vuelve a
leer el inventario completo y escribe atómicamente, sin modificar estado ni
prometer un histórico acumulado. Errores de red y HTTP se propagan.

Licencias, planificación automática y jitter están deshabilitados en manifiesto.
Los métodos de licencias producen cero registros con `disabled=true`.

## Validación reproducible

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_autol -v` — **6 pruebas pasan**.
Cubren agrupación y deduplicación documental, cabecera anidada nº 27, separación
de fechas, ausencia de inferencias desde nombres de archivo, exclusión de
formularios, fallo ante paginación/cambio estructural, contrato del adaptador y
carga del manifiesto.

Extracción real mediante `load_manifest(Path('data/municipios/autol/manifest.yaml'))`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Se activó sólo `portal.config['evidence_dir']` en memoria para guardar el HTML.

Evidencias locales, excluidas de la entrega de código:
`evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/urbanismo.html`,
`evidence/bor-modificacion-27.pdf`, `evidence/bor-modificacion-27.txt`.
La validación contiene recuento real, fuentes, limitaciones y resultado de la
política de entidades. No se ejecutó orquestador, publicación ni acceso a datos
privados. Sólo se añaden los cuatro archivos fuente autorizados.
