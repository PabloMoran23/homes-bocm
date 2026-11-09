# Almogía — INE 29011, Málaga, Andalucía

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes descubiertas y alcance

- Web municipal: <https://www.almogia.es/> y `/urbanismo/` devolvieron HTTP 202 sin contenido utilizable. `http://www.almogia.com` redirige a esa web; el acceso HTTPS al dominio antiguo falla por certificado de nombre de host. No se desactiva la verificación TLS.
- Sede municipal: <https://almogia.sedelectronica.es/transparency>. Accesible, con la categoría «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE (0)». El tablón <https://almogia.sedelectronica.es/board> contiene anuncios de otras materias. No se convierten formularios, convocatorias o anuncios administrativos en proyectos ni licencias concedidas.
- Inventario oficial utilizado: [Consulta de planes urbanísticos y territoriales de Andalucía, SITU@](https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf), publicado por la Junta de Andalucía. La consulta «Planes urbanísticos y territoriales aprobados», municipio `29011`, devuelve **un instrumento de planeamiento general**: NNSS, identificador `399`, aprobación `23/04/97`. El detalle lo identifica como «NNSS - Normas Subsidiarias Municipales», objeto «1997», ámbito municipal ALMOGÍA y estado fuente «Vigente».
- Contraste documental: [BOJA 16 de 25/01/2022, disposición 61](https://www.juntadeandalucia.es/boja/2022/16/61), publicación del texto refundido y otros documentos. Esa publicación posterior no sustituye la fecha de aprobación del instrumento. No se deduce una fecha única de acuerdo para toda la documentación.

El scraper cubre el inventario consultado de planeamiento general aprobado, **no todo el planeamiento ni todas las obras del municipio**. No pretende extraer las modificaciones y figuras de desarrollo de la búsqueda detallada ni el libro de registro. La sede vacía no demuestra que no existan actuaciones en otras fuentes.

## Protocolo y agrupación

Se inicia una sesión anónima, se envía el formulario JSF con `municipiosseleccionados=29011`, `munNomCod=[{"id":"29011","nombre":"Almogía"}]` y `radioButton=aprobado`. El listado utiliza POST a [figuras.jsf](https://ws132.juntadeandalucia.es/situadifusion/pages/figuras.jsf), con `codigos=29011`, `iDisplayStart` e `iDisplayLength=8`. Se recorren las páginas hasta alcanzar el total declarado; cambios de total, páginas vacías prematuras, duplicados o esquemas nuevos provocan error antes de sustituir el resultado anterior. La ejecución observada declara y devuelve un registro.

El identificador del instrumento se descubre en el listado, no se precarga. Mediante los comandos del formulario se abre el detalle y se solicita su enlace público «Compartir url». Ese enlace se conserva en `url`; incluye parámetros codificados por el propio sitio, sin credenciales. Los formularios internos y sus identificadores de sesión no se usan como identificadores persistentes.

El detalle incluye un array JSON `var mapa` que alimenta el árbol y todas las páginas de documentos. Se leen sus 266 entradas, no solo la tabla visible. Tras agrupar por URL quedan **67 documentos distintos**, con memoria, normativa, planos, resolución, publicaciones y corrección de errores. Se conserva cada título, enlace y todas sus `clasificaciones_fuente`. Los planos y las copias de un mismo documento en distintos nodos no se convierten en proyectos nuevos. Las correcciones pertenecientes a la ficha permanecen dentro del mismo instrumento, sin atribuirles la fecha de aprobación del plan.

Se exige coincidencia entre municipio, provincia, figura, identificador y fecha del listado/detalle. Una figura nueva requiere revisión semántica: no se omite silenciosamente.

## Semántica y límites

`fecha_aprob=1997-04-23` procede exclusivamente del campo «Fecha de Aprobación» coincidente en listado y detalle. No se crea `fecha`, `fecha_publicacion`, `fecha_acuerdo` ni una fase a partir del tipo de figura. `estado_fuente` reproduce la clasificación del portal sin certificar vigencia jurídica independiente. El campo de actualización general del sitio no se utiliza como fecha del instrumento.

El manifest usa `proyectos.source=ayuntamiento` para seleccionar el pipeline de portal existente. Los registros identifican expresamente al publicador real mediante `source=junta_de_andalucia`, `organismo_publicador` y `origen`. No se presenta a la Junta como ayuntamiento.

No hay coordenadas ni geometrías extraídas. `publication_ready=false`, `geometry_status=unavailable`, `geocode.jitter_missing=false`, `schedule.enabled=false` y `licencias.enabled=false`. Las actualizaciones son refrescos completos del mismo inventario. Las licencias devuelven salida vacía y estado desactivado.

Los enlaces de descarga pueden necesitar abrir antes la ficha compartida en una sesión anónima. Se verificó precisamente ese comportamiento: una descarga sin contexto devolvió una página HTML de error; después de abrir la ficha pública se descargaron correctamente tres PDF: resolución (`doc=63731`), normas (`doc=63734`) y BOJA normativa (`doc=258363`). Se conservan capturas, archivos y metadatos locales. No se verificó individualmente la descarga de los 67 documentos ni se extrajeron sus geometrías o fechas internas.

## Validación reproducible

Runtime autorizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_almogia -v` — **5 pruebas correctas**, sin red. Cubren agrupación, separación de instrumentos, ausencia de fechas/coordenadas inferidas, rechazo de contenido no verificable y paginación completa o fallida, preservando la salida previa.

Extracción real mediante `load_manifest('almogia')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Resultado: **1 registro real, 67 enlaces documentales únicos**. `evidence/validation.json` contiene `live_records`, URLs, limitaciones, runtime y resultado de la política compartida de entidades. Esta política clasifica el instrumento como categoría desconocida; se deja documentado, sin alterar la política común.

`evidence/live/live-001.txt` a `live-005.txt` conservan las respuestas de inicio, formulario/listado, JSON de inventario, detalle y enlace compartido. Las capturas de descubrimiento y PDF también están en `evidence/`. La evidencia es local y no forma parte de los cuatro archivos fuente solicitados. No se ejecutan pasos de publicación, geocodificación, sincronización ni acceso a bases de datos.
