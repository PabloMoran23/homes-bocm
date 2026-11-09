# San Miguel de Salinas — Alicante — INE 03120

Investigación y extracción real: 9 de noviembre de 2026. Adaptador único:
`municipio.adapters.san_miguel_de_salinas:SanMiguelDeSalinasAyuntamientoAdapter`.

## Descubrimiento y alcance

La página municipal [Urbanismo](https://www.sanmigueldesalinas.es/urbanismo/)
enlaza estos inventarios oficiales, consultados sin autenticación:

- [Planeamiento urbanístico](https://sanmigueldesalinas.sedelectronica.es/transparency/c677279a-ae3b-433c-8660-5bfd3bde9d7e/): sección 1.1, normas subsidiarias, modificaciones y desarrollo (65 documentos); sección 1.2, texto consolidado, rotulada «21 de septiembre de 2023» (29 documentos).
- [Obras públicas e infraestructuras](https://sanmigueldesalinas.sedelectronica.es/transparency/927c1936-4a04-438b-8a23-ace06d3f99a0/): cuatro carpetas de planes de despliegue de fibra óptica de operadores. No se interpretan como obras municipales ejecutadas.
- [Exposición pública](https://sanmigueldesalinas.sedelectronica.es/transparency/da10af8f-39a4-4424-bb71-55c1117e89b6/): proyecto de normalización de fincas de Los Invernaderos, con cinco documentos. No se confunde con el plan parcial del mismo sector.

La extracción implementada cubre **solo la [sección 1.1](https://sanmigueldesalinas.sedelectronica.es/transparency/8d019610-1215-41b6-9d8c-a415d1cbc368/)**:
14 instrumentos y 65 enlaces documentales. Incluye NNSS, modificación puntual 1,
planes parciales ADU 14–19, Lo Quilez, Los Invernaderos, catálogo de bienes y
espacios protegidos, plan especial Las Cuevas, modificación puntual 3 Lo Quilez
II-Ampliación y plan parcial industrial Lo Quilez II-Ampliación.
No es un censo completo de actuaciones ni un histórico municipal. El texto
consolidado, la exposición pública, los planes de telecomunicaciones y el
registro de programas quedan fuera de esta cobertura. No se ha verificado un
registro de licencias concedidas; modelos y solicitudes no son concesiones.

## Navegación, agrupación y procedencia

La tabla `TransparencyListPanel` sirve diez instrumentos inicialmente y cuatro
más mediante «Mostrar más». El adaptador realiza las peticiones Wicket y aplica
únicamente los fragmentos HTML de `component`, sin ejecutar JavaScript. Agota
la paginación en cada carpeta. Una respuesta vacía, cambio de estructura,
paginación que no avanza o límite de seguridad provoca error antes de escribir
la salida, conservando una salida anterior.

La navegación de carpetas devuelve HTTP 200 con cuerpo de un espacio y cabecera
`Ajax-Location`: esta cabecera proporciona la URL pública estable de cada
carpeta. Los tokens temporales se obtienen en cada ejecución, no se fijan en el
código. Se recorren subcarpetas y se contrastan los recuentos anunciados con el
número de documentos recuperados: **10, 7, 6, 3, 8, 2, 2, 3, 6, 6, 4, 3, 4, 1**.
Cada instrumento produce un registro, con ID derivado de su URL de carpeta.
Cada elemento de `documentos` conserva título, URL oficial `preview-document`
y URL de la carpeta de procedencia; memorias, planos y anexos no se convierten
en proyectos independientes. Las dos actuaciones distintas Lo Quilez
II-Ampliación conservan registros separados.

Muestra documental: [Memoria NNSS](https://sanmigueldesalinas.sedelectronica.es/preview-document/afc9fcf3-7c7e-42a6-94fc-7afdcc192702),
ficha HTTP 200, formato PDF y fecha de creación electrónica 29-ene-2024.
Se verificaron además los primeros 1024 bytes del PDF mediante una sesión
anónima nueva: HTTP 200, `application/pdf`, firma `%PDF-`. La URL temporal del
visor exige la sesión de la ficha; los registros retienen la URL estable de la
ficha. No se descargaron ni analizaron los otros 64 documentos.

## Semántica y limitaciones

La presencia en el inventario no acredita vigencia jurídica, aprobación,
concesión o ejecución. No se generan `fecha`, `fecha_publicacion`,
`fecha_acuerdo`, `fecha_aprob`, fase ni coordenadas. Los meses/años de los títulos
se preservan literalmente y no se convierten en fechas; tampoco la fecha de
creación electrónica del documento equivale a una aprobación ni publicación
del instrumento. Se conserva la procedencia municipal, `publication_ready: false`
y `geometry_status: unavailable`. El manifiesto desactiva licencias, ejecución
programada y jitter de geocodificación. La actualización refresca el inventario
completo del alcance definido; no reconstruye documentos retirados ni mantiene
un historial de cambios.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_san_miguel_de_salinas -v
```

Diez tests correctos: paginación, documentos anidados agrupados, aislamiento
entre instrumentos, recuentos, duplicados, cambio de estructura, URL externa,
rechazo de formularios, manifiesto y actualización/licencias desactivadas.

Extracción real mediante `backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
con `config={'capture_dir': 'evidence/source-captures'}`: **14 registros / 65
documentos**. Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas de fuentes, respuestas de paginación,
ficha documental y prefijo PDF. No se usaron bases de datos, despliegues,
publicación ni geocodificación.
