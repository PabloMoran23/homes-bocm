# Derio — INE 48901, Bizkaia

Verificación en vivo: 2026-11-09. Adaptador único de planeamiento municipal,
con cobertura parcial, licencias deshabilitadas y sin ejecución programada.

## Fuentes oficiales e inventario

Punto de entrada: https://www.derio.eus/es/territorio/ (HTTP 200).
La sección «Urbanismo y obras» contiene la biblioteca «Normas subsidiarias»,
el enlace «Derio HAPO PGOU» y el acceso al planeamiento de desarrollo de Bizkaia.
No se usa una noticia individual como inventario ni se confunden formularios,
licitaciones, ordenanzas o propuestas genéricas de actuaciones con proyectos.

1. **Normas Subsidiarias de Derio**: un instrumento con los **29 documentos**
   publicados en la biblioteca municipal: normativa, memoria y planos. Se localiza
   por el título de la galería CatFolders, no por las fechas de sus rutas PDF.
   Las referencias del portal PGOU a las NNSS de 2003 no se convierten en una
   fecha de acuerdo. No se afirma que los documentos municipales incorporen
   todas las modificaciones posteriores del instrumento.
2. **Nuevo PGOU de Derio**: la web municipal enlaza https://hapo-derio.eus/es;
   desde su menú «DOCUMENTACIÓN» se descubre
   https://hapo-derio.eus/es/node/828 (HTTP 200 en ambos casos).
   Esta página publica «Fase 3: Exposición pública (Avance)» y **134 enlaces PDF
   distintos**, incluidos el documento de avance, cartografía, evaluación
   ambiental, información previa y participación. Todos pertenecen a un único
   PGOU y conservan título, URL y página de procedencia. Las alternativas de
   Mantuliz y las propuestas de equipamientos no generan proyectos separados.
   La fase refleja exclusivamente la documentación publicada; no acredita la
   situación administrativa actual completa ni aprobación inicial o definitiva.

La portada del PGOU anuncia exposición del avance del 7 de marzo al 7 de mayo
de 2024. Es un período de exposición, no una fecha de aprobación o publicación
verificada del instrumento: `fecha`, `fecha_publicacion`, `fecha_acuerdo` y
`fecha_aprob` permanecen nulas. Tampoco se interpreta `/uploads/2025/04/` como
fecha administrativa.

## Paginación y límites

La biblioteca NNSS es de tipo `single_folder`: el HTML recibido incluye las 29
filas completas. El JavaScript público CatFolders revisado inicializa DataTables
sobre esas filas; `limit: 10` controla la presentación en cliente. Se recorren
**todas las filas del HTML**, sin aplicar ese límite. La documentación Drupal del
PGOU contiene el inventario completo en su cuerpo, sin paginación activa.
Enlaces de siguiente página o contenedores de paginación provocan un error
explícito; también los cambios del tipo de galería, la ausencia de documentos
fundamentales o el cambio de fase del PGOU. Se requiere revisión si cambia la
estructura o aparece paginación del servidor. Un fallo no sobrescribe la salida
previa. Las actualizaciones vuelven a leer íntegramente ambos inventarios.

Otros inventarios oficiales descubiertos, **no extraídos**:

- https://www.bizkaia.eus/es/planeamiento-urbanistico-buscador — enlazado por
  Derio como planeamiento de desarrollo; registro foral de instrumentos vigentes,
  modificaciones, resoluciones y publicaciones. Pendiente de integración.
- https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-derio
  y su ficha federada
  https://opendata.euskadi.eus/catalogo/-/planeamiento-urbanistico-derio/ —
  datos globales orientativos de planeamiento, no un registro de licencias
  concedidas. No se transforman sus agregados en proyectos.

No se cubren todo el histórico municipal, modificaciones del registro foral,
obras públicas, licencias concedidas ni su situación administrativa completa.
Los enlaces se conservan tal como los publica la fuente, incluso los antiguos;
no se ha descargado ni comprobado individualmente la totalidad de los 163 PDF.

## Geometría

`geometry_status: unavailable`. Los inventarios enlazan planos PDF; no exponen
una geometría vectorial vinculada a cada instrumento que se haya verificado.
No se geocodifica el centro municipal, no se vectorizan planos y no se inventan
coordenadas. `lat`, `lon` y `geometry` nulos; `publication_ready: false`.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_derio -v`, **6 pruebas correctas**.
Verifican agrupación y deduplicación, más filas que el límite visual, exclusión
de formularios y enlaces externos, fechas y geometrías nulas, cambio de fase,
contenido ausente, rechazo de paginación, conservación de salida ante fallo,
licencias deshabilitadas e identidad/flags del manifest.

Extracción real mediante `load_manifest('derio')`, `load_portal_adapter(manifest)`
y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir` local.
Resultado: **2 registros reales**, **29 + 134 enlaces documentales**.
Se descargaron además dos PDF representativos, ambos HTTP 200 y cabecera PDF:
la normativa NNSS del BOB y el documento completo de avance del PGOU.

Evidencias locales, excluidas del commit:
`evidence/proyectos.jsonl`, `evidence/validation.json`, capturas de los tres
inventarios HTML, JavaScript público de la galería y los dos PDF anteriores.
La validación incluye hora UTC, conteos, URLs fuente, limitaciones, comprobaciones
de los documentos de muestra y resultado del guard semántico del registro.
El guard clasifica ambos instrumentos como entidad desconocida; no acredita
promociones inmobiliarias ni habilita su publicación.

Solo se añaden manifest, investigación, adaptador y pruebas propios de Derio.
`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.
Sin dependencias nuevas, fuentes compartidas modificadas ni publicación.
