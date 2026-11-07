# Benetússer — INE 46054, Valencia

Investigación y extracción en vivo: 2026-11-07. Un único adaptador municipal,
limitado a cuatro instrumentos urbanos publicados en el catálogo Benetússer
2030. Son referencias documentales reales, no obras adjudicadas, actuaciones
ejecutadas ni licencias concedidas. No se afirma vigencia jurídica completa.

## Fuentes oficiales e inventarios consultados

- https://www.benetusser2030.es/documentos/ — HTTP 200. Catálogo de documentos
  municipales con todos los apartados desplegables presentes en el HTML; no se
  observó paginación. Publica planes de diversas áreas, no un registro exhaustivo
  de proyectos urbanísticos. Capturas `evidence/discovery-3.html` y
  `evidence/live-catalogue.html` (esta última es la respuesta exacta de la
  extracción real del adaptador).
- https://www.benetusser2030.es/aviso-legal/ — HTTP 200. Identifica al Ayuntamiento
  de Benetússer, CIF P4605400C; el sitio se presenta como iniciativa municipal
  mediante su Agència de Desenvolupament Local. Su aviso distingue información
  orientativa de publicaciones con validez legal. Captura `discovery-4.html`.
- https://benetusser.sede.dival.es/default.aspx — HTTP 200, sede del mismo
  Ayuntamiento y CIF; enlaza la web principal y su portal de transparencia.
- https://benetusser.sede.dival.es/tablondeanuncios/ — HTTP 200. Inventario público
  actual con seis anuncios: personal, convocatoria, festivos, ayudas y vehículos
  DANA. No se observó un inventario urbanístico aprovechable ni licencias
  concedidas. Captura `discovery-2.html`. No se convierten esos anuncios en obras.
- https://www.benetusser.es/es/transparencia y https://benetusser.es/es — la
  conexión se cierra sin respuesta HTTP. También fallaron la portada con www
  y las tres referencias documentales de ese dominio descritas abajo.
- El resultado de búsqueda de una solicitud de urbanismo en la sede es un
  formulario, no evidencia de una licencia concedida. No se extrae. Las noticias
  sobre modificaciones del PGOU y las referencias a contratación no se usan
  como inventario de proyectos.

## Cuatro instrumentos extraídos

Cada registro procede del título y de los enlaces de su propio apartado del
catálogo. Se conserva el título literal y todos los enlaces documentales,
agrupando apartados repetidos del mismo instrumento y eliminando únicamente
enlaces exactamente duplicados. `url` y `documentos[].url_origen` identifican
el catálogo; `documentos[].url` conserva la referencia específica, incluida
cualquier consulta de descarga. Se distingue PDF de página de acceso.

1. **Agenda Urbana de Reconstrucción de Benetússer Post-DANA 2024**:
   https://www.benetusser2030.es/wp-content/uploads/2024/07/Benetusser-AgendaReconstruccion.docx_compressed.pdf
   — HTTP 200, application/pdf, 4.867.722 bytes. Se leyó el PDF: portada fechada
   «Enero 2026», promotor Ayuntamiento de Benetússer y resumen que lo describe
   como instrumento estratégico para la recuperación integral y reconstrucción
   urbana. Se extrae el instrumento completo, sin transformar cada propuesta en
   una obra aprobada. La ruta `2024/07` no acredita publicación ni acuerdo; el
   año 2024 del título identifica la DANA. La portada tampoco establece un día
   de aprobación. Capturas `agenda-reconstruccion.pdf`,
   `agenda-reconstruccion-live.pdf` y texto de lectura `agenda-reconstruccion.txt`.
2. **PGOU Plan General de Ordenación Urbana (1990)**:
   https://www.benetusser.es/es/pagina/plan-general-ordenacion-urbana-pgou
   — referencia del catálogo a la página del instrumento; conexión cerrada sin
   respuesta. No se interpreta como enlace directo a PDF ni se presume acceso
   al expediente completo o a sus modificaciones.
3. **PUAM Plan Urbano de Actuación Municipal 2022**:
   https://www.benetusser.es/sites/www.benetusser.es/files/54153_PUAM%20Benetusser%20%28f%29.pdf%20-%20Copia%20autentica.pdf
   — enlace PDF publicado en el catálogo; conexión cerrada sin respuesta.
4. **EMUS Programa de movilidad urbana sostenible 2018**:
   https://www.benetusser.es/sites/default/files/emus_benetusser_definitivo_0.pdf
   — enlace PDF publicado en el catálogo; conexión cerrada sin respuesta.

Los tres últimos registros acreditan la referencia municipal al instrumento,
no la disponibilidad del documento ni su vigencia o aprobación. Los años de
sus títulos no se convierten en fechas completas. Tampoco se convierten los
números presentes en nombres de archivos en expedientes administrativos.

## Alcance y comportamiento

Se excluyen los otros documentos del catálogo sobre igualdad, inclusión,
comercio, residuos, emergencias, energía y recuperación económica. La cobertura
de estos cuatro instrumentos es parcial: no enumera todas las obras físicas,
modificaciones del PGOU, expedientes ni actuaciones posteriores del municipio.
PGOU es planeamiento urbanístico; PUAM, EMUS y la Agenda son instrumentos de
planificación y acción urbana, sin atribuirles el mismo carácter normativo.

Los campos `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase`
quedan nulos porque el catálogo no acredita esos datos. No se utilizan el reloj
de la sede, la fecha de extracción, el copyright o las carpetas de los archivos.
Sin geometría contrastada: `lat`, `lon` y `geometry` nulos,
`publication_ready: false`. No hay centroides ni coordenadas inventadas.
Manifest: `licencias.enabled`, `schedule.enabled` y `geocode.jitter_missing`
son false; municipio y provincia exactos, INE 46054.

El adaptador hace una petición HTTPS al catálogo, verifica respuesta HTML y
destino, timeout de 40 segundos y límite de 3 MB comprobado por streaming. No
descarga los PDF para interpretar sus fechas. Los enlaces se conservan como
referencias del inventario, incluso cuando la web principal está caída. Las
comprobaciones independientes de disponibilidad están en `validation.json`.

No hay límite de filas ni corte de páginas: esta fuente actualmente es una sola
página completa. Si aparecen controles de paginación/continuación, falta alguno
de los cuatro instrumentos revisados, cambia la estructura o desaparecen sus
documentos, se produce un error antes de escribir la salida. Un nuevo formato
o una nueva página requiere revisión del parser. Las actualizaciones refrescan
el snapshot completo; no se deduce un cursor incremental de fechas inexistentes.
Las identidades de los cuatro instrumentos no dependen del orden ni de sus PDF.

## Validación local

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_benetusser -v`: **5 pruebas pasadas**. Comprueban
  selección de instrumentos y exclusión de formularios/licitaciones/planes
  sociales, fechas y geometría nulas, agrupación sin pérdida de documentos,
  rechazo de continuación y de inventarios incompletos, origen de documentos,
  manifest, escritura del snapshot, actualización y licencias deshabilitadas.
- `BenetusserAyuntamientoAdapter.backfill_proyectos`, configurado desde el
  manifest y con red real: **status ok, 4 registros**, sin utilizar fixtures.
- `evidence/proyectos.jsonl`: registros reales. `evidence/validation.json`:
  `live_records: 4`, URLs consultadas, captura exacta y SHA-256, comprobaciones
  de los cuatro enlaces, resultados y limitaciones. Todo `evidence/` es local
  y no forma parte de los cuatro archivos fuente entregables.

No se modifican componentes compartidos, dependencias ni configuración de
despliegue. No se accede a credenciales, bases de datos o publicación.
