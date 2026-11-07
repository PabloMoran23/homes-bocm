# Tarancón, Cuenca — INE 16203

Investigación y ejecución en vivo: 7 de noviembre de 2026.

## Fuentes oficiales y alcance

La web oficial https://www.tarancon.es redirige a https://nuevaweb.tarancon.es/.
Su página https://nuevaweb.tarancon.es/normativa/ enlaza dos carpetas públicas de
transparencia. La de Normas Subsidiarias es:

https://tarancon.sedelectronica.es/transparency/b2c2d540-4140-4c21-adfa-3e98cbf24323/

Es el inventario **8. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE /
8.3. NORMATIVA URBANÍSTICA**, con tres tomos de las NNSS y dos carpetas:
Modificaciones Puntuales a las Normas Subsidiarias (7 documentos) y Estudios de
Detalle (7 documentos). También incluye guía patrimonial y carta arqueológica,
que se excluyen por no identificar instrumentos urbanísticos de esta cobertura.
Los tres tomos se agrupan en un instrumento; memoria, planos y anuncio con el
mismo título base se agrupan conservando todos sus enlaces de previsualización.

La extracción real devuelve **12 instrumentos y 17 documentos**:

- Normas Subsidiarias de Tarancón (tres tomos).
- Modificaciones 17 (Avda. Miguel de Cervantes 49), 24 (UE-30), 26 (OR-6),
  1 del PP SAU RU 2 (parcelas C-02/C-03), 28 (OR-10), 23 (OR-7), 27 (OR-1/OR-4).
- Estudios de detalle: manzanas 82979 y 83971 del SAU RU 2; Peña el Águila,
  Molino de Viento y Juan León Sáez Montalvo (dos documentos); La Noria,
  Peña del Águila, Dámaso Alonso y Molino de Viento OR-4-2 (tres documentos).

Cobertura parcial: documentos publicados en esta carpeta actual, sin afirmar
que sea un registro exhaustivo del planeamiento, de las obras o de expedientes
históricos. No se interpreta el número de modificación como número de expediente.
Se declara `source_entity_type: documento`; la política compartida los reconoce
como documentos sin identidad acreditada de actividad. No se modifica esa política.

La sede https://tarancon.sedelectronica.es/info.0 expone un catálogo de trámites,
incluidas solicitudes urbanísticas. No acredita licencias concedidas y no se usa
como registro. Tampoco se convierten ordenanzas fiscales, anuncios de contratación,
noticias generales ni propuestas participativas en actuaciones aprobadas.

## Acceso, integridad y procedencia

La sede usa enlaces Wicket efímeros en las carpetas. Un GET público con parámetro
`snapshot` único crea una sesión anónima nueva y evita callbacks cacheados de otra
sesión (que pueden devolver una respuesta vacía). Se siguen únicamente los callbacks
de carpeta extraídos del HTML actual, con la misma sesión y sin cabeceras AJAX;
responden con páginas HTML completas. No se persisten los callbacks como identidad:
los documentos conservan sus URL estables `/preview-document/<uuid>`.

Se recorren ambas carpetas, se comprueba cada recuento anunciado y se rechazan
carpetas faltantes, subcarpetas inesperadas o nuevos controles de paginación. No
se observa paginación en el inventario actual. Un cambio de estructura o recuentos
interrumpe la extracción antes de escribir resultados incompletos.

Se comprobó además la previsualización del Tomo I:
https://tarancon.sedelectronica.es/preview-document/22fa816a-d2cf-42a9-a0cb-ddae7971fa6e
respondió HTTP 200 y mostró el nombre del documento, formato PDF e información
de integridad. Su «Fecha de creación 16-nov-2023» es metadato documental y **no**
se usa como aprobación ni publicación. No se descargaron ni interpretaron todos
los PDF; la extracción se basa en las etiquetas y descripciones del inventario.

## Fechas y geometría

`fecha` permanece nula. Las fechas BOP/DOCM de las etiquetas se registran como
`fecha_publicacion`, con procedencia en cada documento. No se deducen fechas de
acuerdo a partir de publicaciones ni de fechas del CMS.

El documento del estudio de detalle Peña el Águila publicado en DOCM 20231027
incluye la descripción municipal: «Acuerdo del Pleno, de fecha 11/10/2023, por el
que se aprueba definitivamente expediente de estudio de detalle». Por ello solo
ese instrumento tiene `fecha_acuerdo` y `fecha_aprob` 2023-10-11 y fase de aprobación
definitiva; su publicación es 2023-10-27. Otros instrumentos mantienen esas fechas
y fase nulas. La descripción original se conserva en `descripcion_fuente`.

No se afirma vigencia actual ni ejecución física. Sin coordenadas o geometría
verificadas: `lat`, `lon`, `geometry` nulos, `publication_ready: false`.
Licencias, programación y jitter de geocodificación desactivados en el manifiesto.

## Validación reproducible y evidencia local

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_tarancon -v` — cuatro pruebas correctas,
incluyendo agrupación, aislamiento de instrumentos, estabilidad de IDs, fechas,
fuentes incompletas, paginación inesperada y manifiesto.

Ejecución real mediante `load_manifest('tarancon')`, `load_portal_adapter(manifest)`
y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, pasando
`manifest.portal.config['capture_dir'] = 'evidence'` para guardar capturas.
`update_proyectos` refresca el inventario completo; no depende de un cursor que
pueda omitir documentos. Las pruebas de parser son locales y no requieren red.

Evidencia local, fuera de los cuatro ficheros fuente: `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas `inventory-root*.html` y
`inventory-folder-*.html`, `normativa.html` y `preview-tomo-i.html`.
La validación incluye recuentos, enlaces de origen, resultado de la política
compartida y limitaciones. No hay publicación, base de datos ni geocodificación.
