# Osuna — INE 41068, Sevilla

Investigación y extracción real: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y alcance

Fuente implementada: [Modificaciones aprobadas del PGOU y planes parciales](https://transparencia.osuna.es/es/transparencia/indicadores-de-transparencia/indicador/Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00027/), portal de transparencia del Ayuntamiento de Osuna. El título de la sección no demuestra el estado de cada instrumento: mezcla avances, aprobaciones iniciales y documentos posteriores. Son expedientes documentales de planeamiento, no licencias concedidas ni obras ejecutadas.

Se consultó también [PGOU del portal municipal](https://www.osuna.es/es/Urbanismo/servicios-municipales/pgou/), cuya respuesta HTML muestra las secciones Avance y Documento Inicial Estratégico sin enlaces PDF directamente extraíbles. La búsqueda oficial identifica además el [indicador PGOU](https://transparencia.osuna.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00027/) y el portal participativo PGOM. No se integran estos inventarios adicionales: el adaptador cubre exclusivamente la sección documentada de modificaciones, con el avance PGOM que esta publica. No pretende cubrir todo el planeamiento municipal.

## Extracción y agrupación

La galería OpenCMS `galleryfiles-1-1` publica ocho páginas con el parámetro `pagegalleryfiles-1-1`. Se siguen los enlaces y se recorre todo el rango anunciado por el enlace de última página; no existe un límite silencioso de registros. Una estructura inesperada, respuesta vacía, paginación desconocida o página repetida provoca error antes de reemplazar el fichero de salida. La actualización vuelve a extraer la instantánea completa; no usa fechas como cursor.

Resultado vivo: **11 instrumentos, 70 URLs documentales únicas encontradas, 68 adjuntos retenidos**. El documento del hospital aparece repetido en todas las páginas y se deduplica. Cada adjunto conserva título literal, URL e inventario de procedencia. Un registro contiene todos los adjuntos identificados del instrumento, incluso de distintas páginas o fases; su URL principal es el primer adjunto descubierto y su ID estable representa el instrumento, no el orden del listado.

| Instrumento | Adjuntos |
| --- | ---: |
| Delimitación PMS parque arqueológico Alcazaba | 3 |
| Estudio de ordenación P.I.-7 Las Vegas | 3 |
| Modificación NNSS construcciones permanentes Recinto Ferial/La Quinta | 12 |
| Modificación PGOU/NNSS ampliación Hospital Comarcal | 8 |
| Avance PGOM Osuna | 2 |
| Modificación NNSS ampliación PI-7 | 10 |
| Delimitación PMS ampliación Ermita Santa Ana | 2 |
| Modificación NNSS Ermita Santa Ana | 6 |
| Cambio de uso a vivienda protegida de varias parcelas | 2 |
| Plan especial EDAR Puerto de la Encina | 16 |
| Modificación NNSS artículo 117, usos en área de servicio | 4 |

El estudio de ordenación Las Vegas y la modificación para ampliación del PI-7 son instrumentos diferentes aunque comparten ámbito. También son diferentes la delimitación PMS y la modificación NNSS de Santa Ana. Los títulos de registros normalizan la identidad; los documentos conservan la redacción original.

## Comprobación documental y fechas

Se descargaron nueve PDFs de comprobación (incluido uno vacío), con sus URLs, tamaños, estado HTTP y firma PDF registrados en `evidence/document-checks.json`. Los ocho válidos se convirtieron localmente a texto mediante `pdftotext`, sin instalar software. Las capturas PDF y texto quedan en `evidence/`.

Estas lecturas permiten resolver dos títulos ambiguos mediante reglas exactas:

- `ACUERDO PLENO APROBACION INICIAL`: el PDF identifica P2511251003, delimitación PMS ampliación Ermita Santa Ana. Acuerdo de sesión 25/11/2025; firma 03/12/2025.
- `1104-2016 ACUERDO PLENO P1609261013.-MODIFICACION PUNTUAL NNSS-1`: artículo 117, usos PI-3 y PI-4. Acuerdo 26/09/2016; firma 27/09/2016. Se contrastó también el acuerdo definitivo P1701301004 del mismo instrumento.

El documento rotulado `Ampliación P17` dice en su contenido «AMPLIACIÓN PI7 LAS VEGAS», lo que confirma su agrupación con la modificación PI-7. `7EDAR VALORACION IMPACTO SALUD SINTESIS` y `EDAR ACUERDO` identifican el plan especial EDAR Puerto de la Encina en su contenido.

El acuerdo Alcazaba recoge sesión 28/09/2026 y firma 07/10/2026. El certificado del avance PGOM recoge sesión 03/02/2026 y firma 09/02/2026. **Firma, sesión y publicación son conceptos distintos**: ninguna fecha de firma, código de expediente, nombre de fichero ni actualización del CMS se convierte en fecha de aprobación/publicación. El adaptador no extrae fechas ni fases. Las fechas anteriores son comprobaciones de investigación, no campos precargados de los registros.

## Limitaciones y exclusiones

Dos documentos se enumeran explícitamente como no clasificados en `validation.json`:

- `REGISTRO PLANEAMIENTO enero2016`: es un registro agregado histórico; no se convierte en proyecto ni se extraen sus entradas.
- `DOCUMENTO VALORACION IMPACTO EN SALUD. CONSTRC. PERMANENTES`: respondió HTTP 200 con **cero bytes**. Sin contenido verificable ni identidad suficiente en su título, no se asocia por proximidad.

No se verificó la descarga de todos los 68 adjuntos retenidos; los enlaces publicados son evidencia de inventario, no garantía de disponibilidad del contenido. Las reglas cubren identidades revisadas, y los futuros títulos desconocidos se comunican en `unclassified_documents`; una nueva identidad exige revisión. No se incluyen formularios, licitaciones o noticias como proyectos. Licencias desactivadas por ausencia de registro público de concesiones verificado.

Sin coordenadas, geometría ni fechas inventadas. Todos los registros llevan `publication_ready: false` y `geometry_status: unavailable`. El manifiesto fija `schedule.enabled: false`, `geocode.jitter_missing: false`, `licencias.enabled: false`, municipio Osuna, provincia Sevilla y código INE `41068`.

## Validación reproducible

Pruebas: `.../venv/bin/python -m unittest municipio.test_osuna -v`: **6 pruebas correctas**. Cubren agrupación entre páginas, aislamiento de instrumentos, adjunto PI-7 con sufijo, exclusiones, falta de fuentes, paginación completa, rechazo de páginas repetidas sin sobrescribir, manifiesto y carga mediante registry.

Extracción real mediante `load_portal_adapter(load_manifest('osuna')).backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `adapter.config['capture_dir']='evidence'`. El registry aplica la política compartida existente: 11 entidades, cero desconocidas, estado `ok`. No se modificó ningún módulo compartido.

Evidencia local sin commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, ocho capturas `inventory-N.html`, capturas de descubrimiento y comprobaciones documentales. No se ejecutó ningún paso de base de datos, publicación o despliegue.
