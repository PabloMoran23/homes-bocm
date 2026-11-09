# Entrambasaguas — Cantabria — INE 39028

Verificado en vivo el 2026-11-09 con el Python preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Implementado un adaptador de inventario documental municipal. Resultado: un
instrumento real, las Normas Subsidiarias de Planeamiento Municipal, con tres
adjuntos conservados en `documentos`. Es cobertura parcial, no un censo completo
de proyectos, licencias u obras. `publication_ready` es false.

## Fuentes oficiales descubiertas

- https://entrambasaguas.org/ — HTTP 200. Identifica el Ayuntamiento de
  Entrambasaguas, Cantabria; enlaza Normativa Urbanística, sede, tablón,
  transparencia, actas y perfil del contratante.
- https://entrambasaguas.org/normativa-urbanistica — HTTP 200. Inventario Drupal
  con tres filas: Planos, Normativa y planos, Memoria. Pertenecen a las mismas
  Normas Subsidiarias, no a tres proyectos diferentes. La respuesta HTML contiene
  los adjuntos aunque algunos extractores de texto no los muestran. Sin paginación
  en esta sección en la consulta realizada.
- https://entrambasaguas.sedelectronica.es/transparency — HTTP 200. La categoría
  «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» muestra cero documentos.
  No permite concluir que no existan otros instrumentos fuera de ese inventario.
- https://entrambasaguas.sedelectronica.es/board/ — HTTP 200. Primera pantalla con
  anuncios de padrón, ordenanzas fiscales y actas antiguas; botón «Mostrar más».
  No se cosecha el tablón ni se afirma haber agotado su paginación. Las actas o
  formularios no se convierten en licencias o proyectos. No se usa contratación
  como sustituto de proyectos técnicos.

## Documentos y procedencia

Todos están enlazados directamente desde el inventario municipal:

- https://entrambasaguas.org/sites/default/files/2022-02/NORMAS-SUBSIDIARIAS-DE-PLANEAMIENTO-MUNICIPAL-Planos.zip
  — HTTP 200, 8.812.106 bytes, ZIP válido. Nueve PDF: ordenación territorial y
  planos de El Bosque, La Rañada, Elechino, Hornedo, Hoznayo, Navajeda/Riestre/La
  Maza, Puente Agüero y Santa Marina. Se conserva el ZIP, sin inventar enlaces a
  sus miembros.
- https://entrambasaguas.org/sites/default/files/2022-02/NORMAS-SUBSIDIARIAS-DE-PLANEAMIENTO-MUNICIPAL-Normativa-y-planos.pdf
  — HTTP 200, 7.154.810 bytes, cabecera PDF verificada.
- https://entrambasaguas.org/sites/default/files/2022-02/NORMAS-SUBSIDIARIAS-DE-PLANEAMIENTO-MUNICIPAL-Memoria.pdf
  — HTTP 200, 2.107.180 bytes, cabecera PDF verificada. Texto de portada:
  Normas Subsidiarias de Planeamiento Municipal, Memoria, Cantabria.

El título del registro deriva del título común de las filas. Cada adjunto conserva
su título, URL, formato y página de procedencia. El identificador estable designa
este instrumento y no se presenta como número de expediente oficial.

## Semántica y límites

No se extraen fechas del directorio `2022-02`, metadatos de descarga o fecha de
consulta. `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan null: el
inventario no las identifica. Tampoco se deduce fase, aprobación definitiva ni
vigencia consolidada a partir del nombre «Normas». No se han reconciliado posibles
modificaciones posteriores con BOC o un registro autonómico. Los planos PDF no
se transforman en coordenadas: latitud, longitud y geometría quedan null.

El parser exige contenido municipal y filas documentales con título de este
instrumento y adjuntos oficiales. Agrupa y deduplica sus enlaces. Un instrumento
distinto, un inventario vacío, cambios de estructura, enlaces inesperados o
paginación provocan error para revisión en lugar de resultados parciales
silenciosos. Update refresca el inventario completo; no es un histórico de eventos.
Licencias, programación y jitter están desactivados en el manifest.

## Validación reproducible

- `.../venv/bin/python -m unittest municipio.test_entrambasaguas -v`: cuatro
  pruebas pasaron. Cubren agrupación/deduplicación, exclusión de navegación y
  formularios, fechas nulas, paginación, fuentes vacías o ajenas, manifest,
  escritura, rechazo de redirección y licencias desactivadas.
- Llamada real a `EntrambasaguasAyuntamientoAdapter.backfill_proyectos`:
  status ok, un registro, tres documentos. Sin mocks en la extracción real.
- Evidencia local en `evidence/proyectos.jsonl`, `evidence/validation.json`,
  HTML del inventario, portada, tablón y transparencia, los tres adjuntos,
  `memoria-first-pages.txt` y `planos-members.txt`. Validation incluye URLs,
  recuentos, fecha de consulta, tamaños, hashes SHA-256 y limitaciones.
  La evidencia es local y no se añade como fuente versionada.
