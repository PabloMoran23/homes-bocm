# O Grove — INE 36022, Pontevedra (Galicia)

Verificación en vivo: 2026-11-07. Adaptador exclusivo para este municipio.

## Descubrimiento y fuentes oficiales

La página municipal de Urbanismo
<https://concellodogrove.es/contido.html?id=36&submenu=31> enlaza en su
navegación «Plans e proxectos» y muestra un acceso al PXOM.
El inventario institucional es
<https://concellodogrove.es/contido.html?id=80&submenu=23>.
Su contenido principal enumera el PXOM y el «Plan especial porto do Grove e da
Illa da Toxa», además de un proyecto ornitológico y un plan de igualdad que no
se extraen: su mención no acredita una obra física ni un instrumento urbanístico.
Se excluyen los banners, noticias, formularios de licencias y contrataciones.

El enlace del inventario conduce a
<https://www.concellodogrove.es/pxom/pxom.php> (también disponible sin www).
Es un catálogo documental municipal, no una noticia aislada. Contiene secciones
plegables para las Normas Subsidiarias y las versiones PXOM 2014, 2020 y 2026.
Se siguen los enlaces publicados por el inventario; no se fabrican rutas PDF.

## Registros y agrupación

La ejecución real produce **3 instrumentos**:

- Plan especial porto do Grove e da Illa da Toxa: 6 documentos (memoria y planos).
  No se atribuye fase, fecha de aprobación ni publicación: el inventario no las indica.
- Normas Subsidiarias de Planeamento: 11 enlaces de planos en Google Drive,
  publicados por el ayuntamiento. La página dice «Aprobadas 25-04-1996»;
  se conserva como fecha de acuerdo, sin atribuir vigencia actual.
- Plan Xeral de Ordenación Municipal: 181 enlaces, con etiqueta de versión,
  agrupando 2014, 2020 y 2026 en un único instrumento. Se conservan las notas
  municipales de cada versión, los informes sectoriales, carpetas, fichas, normas
  y planos, incluidos los 60 enlaces de áreas de imagen. Los atributos HTML
  `coords` son píxeles de navegación, no coordenadas geográficas, y no se extraen.

Los duplicados de URL dentro de cada sección se agrupan. Se preservan queries y
resource keys de Drive; no se rompen enlaces al normalizarlos. Los documentos
retienen `source_url` y los del PXOM también `version`. Los IDs del instrumento
son estables frente a cambios de orden y a la incorporación de nuevas versiones.

La versión 2026 dice «Documento para aprobación definitiva (maio 2026).
Aprobado provisionalmente polo Pleno do 15/06/2026». Se extrae
`fecha_acuerdo=2026-06-15` y `fase=aprobacion_provisional`: no acredita aprobación
definitiva. La fecha de publicación municipal se desconoce y se omite; no se usa
la fecha de captura ni las fechas incluidas en nombres de archivo como aprobación.
Las notas históricas de 2014 y 2020 se mantienen como texto de procedencia.

## Cobertura y límites

Cobertura parcial: inventarios documentales accesibles actualmente en estas dos
páginas, con versiones históricas. No es un registro exhaustivo de todas las obras,
expedientes ni licencias municipales. La presencia de un documento no prueba
vigencia legal o ejecución material. La consulta autonómica
<https://siotuga.xunta.gal/siotuga/urb> identifica las Normas Subsidiarias de O Grove
como suspendidas; por ello el catálogo histórico municipal no se interpreta como
planeamiento vigente. No se usa esa tabla como fuente de nuevos registros.

No hay paginación en los inventarios revisados. Todos los enlaces de las listas y
mapas de imagen se recorren, sin límite numérico. Si aparece paginación reconocible
(`rel=next` o enlaces de siguiente), el parser falla explícitamente. También falla
si desaparece el inventario, la lista del puerto, los documentos, el PXOM o las
Normas, o si aparecen secciones de instrumento desconocidas. Nuevas versiones
anuales PXOM se agrupan automáticamente. Los enlaces a carpetas se conservan,
pero no se recorre su contenido; tampoco se extraen todos los enlaces internos de
los PDFs. La cobertura documental se limita a enlaces directos del catálogo.

Las URL de Drive son enlaces publicados por el municipio; no se ha verificado
individualmente su disponibilidad o titularidad. Los enlaces PDF municipales
tampoco se descargan todos en cada actualización. Se comprobó en vivo el índice
PXOM 2026: HTTP 200, firma PDF, 395200 bytes; captura en evidence/.

`geometry_status: unavailable`: hay cartografía en PDF, pero no se ha verificado
una capa vectorial, CRS ni geometría enlazable por ID de instrumento. No se han
vectorizado planos, inferido centroides ni generado coordenadas. El visor regional
no se usa para atribuir geometrías a los registros. `publication_ready=false`.

Licencias deshabilitadas: no se ha comprobado un registro de concesiones. Ambos
métodos de licencias escriben un archivo vacío. La actualización de proyectos es
una instantánea completa; no infiere bajas ni lleva histórico incremental.
`schedule.enabled=false` y `geocode.jitter_missing=false`.

## Validación reproducible

Runtime solicitado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_o_grove -v
```

3 pruebas pasan: agrupación/versiones/procedencia y fechas; rechazo de paginación,
secciones ausentes y cambios de estructura; contrato del adaptador y manifest.
Las pruebas usan HTML sintético aislado y no requieren red ni evidence/.
La extracción real se ejecutó con `OGroveAyuntamientoAdapter('o-grove',
config={'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/plans.html`, `evidence/pxom.html`,
`evidence/urbanismo.html` y `evidence/pxom-2026-index.pdf`. El informe contiene
`live_records=3`, fuentes, recuentos documentales y limitaciones. No se han cambiado
fuentes compartidas, dependencias, registro de adaptadores ni configuración global.
