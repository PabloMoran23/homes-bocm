# Cazorla — INE 23028, Jaén, Andalucía

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales examinadas

- Portada municipal: https://cazorla.es/ . Enlaza directamente el inventario IDAE y el PSTD.
- Inventario implementado: https://cazorla.es/proyectos-que-favorecen-una-economia-baja-en-carbono-idae/ . Tabla municipal con denominación y alcance, número de expediente IDAE, inversión y financiación de cinco actuaciones físicas de eficiencia energética. No es una convocatoria ni un anuncio de contratación.
- https://cazorla.es/urbanismo/ : formularios y guías para trámites, sin inventario de licencias concedidas. Se excluye.
- https://cazorla.es/edictos-y-ordenanzas/ : lista mixta de ordenanzas, anuncios y documentos históricos; contiene referencias a planeamiento y proyectos, pero no se extrae en este adaptador acotado.
- https://cazorla.es/pstd/ : inventario documental y noticias del Plan de Sostenibilidad Turística. Incluye actuaciones materiales, servicios y documentos de distintas fechas, además de un bloque de noticias paginado («Entradas más antiguas»). Se examinó para descubrimiento, pero queda enteramente fuera de la cobertura implementada; no se presenta su primera página como inventario completo.
- La portada enlaza la sede https://cazorla.sedelectronica.es/transparency . No se ha verificado allí un registro utilizable de concesiones y no se extrae.

## Cobertura y unidad de registro

Cinco registros reales extraídos en vivo mediante `load_portal_adapter(load_manifest('cazorla'))` y `backfill_proyectos`:

| Expediente IDAE | Actuación del inventario |
| --- | --- |
| 5716 | Sustitución de enfriadoras por bombas de calor en el Ayuntamiento |
| 5711 | Instalaciones fotovoltaicas en los CEIP Virgen de la Cabeza y San Isicio y monasterio Montesión |
| 5691 | Luminarias y sistemas de control en edificios municipales |
| 5688 | Sustitución del alumbrado público por LED en Cazorla y pedanías identificadas en la fuente |
| 5660 | Rehabilitación energética de la envolvente del edificio de la piscina municipal |

Se transcribe el título completo de cada fila y sus importes originales. Un expediente es un registro, aunque incluya varios edificios o localidades. Los ID son estables por expediente; las filas repetidas compatibles agrupan enlaces documentales y las incompatibles provocan error. Cada registro conserva el documento HTML municipal y un localizador por número de expediente; la tabla actual no contiene anexos técnicos individuales. Si aparecieran enlaces en sus filas se conservarían agrupados en el expediente correspondiente, sin descargarlos automáticamente.

El inventario IDAE observado es una sola tabla estática de cinco filas, sin paginación. No se fija un límite de registros; se leen todas las filas. Una tabla vacía, cambio de estructura, fila incompleta, conflicto de expediente o paginación detectada provoca error antes de escribir la salida. El adaptador no recorre noticias ni otras secciones de la web.

## Semántica y límites

Cobertura **parcial**, limitada al inventario municipal IDAE; no es un censo de todos los proyectos ni del planeamiento de Cazorla. La narrativa municipal dice que IDAE resolvió favorablemente las cinco solicitudes en 2022 y describe actuaciones en desarrollo. No permite verificar una fecha exacta de acuerdo ni el estado actual de ejecución: no se generan `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` ni `fase`. Las fechas de subida de imágenes y las del CMS tampoco se convierten en aprobaciones.

Los importes se conservan como texto tal como aparecen. No se recalculan las columnas a partir del encabezado 80%/20%; la fila 5691 muestra una distribución distinta de esos porcentajes. No se certifican subvenciones ni se interpreta esta publicación como concesión de licencia.

Sin coordenadas verificadas; `geometry_status: unavailable` y `publication_ready: false`. Licencias, programación y jitter desactivados en el manifest. El envoltorio compartido de la registry añadió su clasificación de entidades: cinco categorías desconocidas, estado de política `ok`; no es validación independiente ni autorización de publicación.

## Validación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Comando de tests: `-m unittest municipio.test_cazorla -v`: **5 tests correctos**. Comprueban procedencia y semántica, agrupación y aislamiento de documentos, lectura sin límite fijo (60 filas), rechazo de vacíos/cambios/conflictos/paginación y carga real del manifest/adapter.

Extracción real ejecutada con el adaptador resuelto por el manifest y `config['evidence_dir']='evidence'`, sin base de datos ni publicación. Resultado: **5 registros**. Evidencias locales, no destinadas a commit:

- `evidence/proyectos.jsonl`: registros reales, incluida anotación de la política compartida.
- `evidence/validation.json`: fecha UTC de ejecución, `live_records`, `source_urls`, limitaciones y SHA-256 de la captura.
- `evidence/idae-live.html`: respuesta HTML utilizada por la extracción real.
- `evidence/home.html`, `urbanismo.html`, `edictos.html`, `idae.html`, `pstd.html`: capturas de descubrimiento.

Solo se añaden los cuatro archivos fuente solicitados. Sin cambios compartidos, dependencias nuevas, geocodificación ni operaciones de publicación.
