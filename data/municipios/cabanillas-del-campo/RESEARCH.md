# Cabanillas del Campo — Guadalajara — INE 19058

Verificación en vivo: 2026-11-07. Adaptador único de inventario documental del
Plan de Ordenación Municipal (POM). Cobertura **parcial**, no registro de licencias
ni inventario exhaustivo de obras públicas.

## Descubrimiento y fuentes oficiales

- [Urbanismo municipal](https://aytocabanillas.org/ayuntamiento/normativa/urbanismo/)
  enlaza tanto el POM como el apartado de planeamiento de la sede electrónica.
  También enlaza trámites y solicitudes: estos no son licencias concedidas y se excluyen.
- [Urbanismo y Obras](https://aytocabanillas.org/urbanismo-y-obras/)
  advierte del carácter informativo de la documentación y de posibles modificaciones.
- [Inventario del POM](https://aytocabanillas.org/ayuntamiento/normativa/urbanismo/pom/):
  HTTP 200, 20 planos PDF en `#modulo-pom` y una memoria/normas bajo el rótulo
  «Memoria POM 2010» en `#modulo-enlace-archivos`. Se conservan las etiquetas y URLs
  originales, incluso las aparentes discrepancias de rótulo/nombre de archivo.
- [Planeamiento y normativa en transparencia](https://cabanillasdelcampo.sedelectronica.es/transparency/19e73073-230f-4f4c-bd85-e7ee8099c1b0/):
  HTTP 200, tres fichas estables `preview-document/<UUID>` en el nivel raíz:
  publicación BOP del texto refundido (23-12-2025), anuncio DOCM (24-02-2026) y
  corrección de errores BOP (07-10-2026). Cada ficha ofrece visor y descarga PDF.

El inventario de transparencia también anuncia carpetas dinámicas Wicket: POM
2005 (26), modificaciones aprobadas (8), planes de desarrollo (10), especiales (2)
y modificaciones en tramitación (2). **No se extrae su contenido** ni se interpreta
su contador como número de instrumentos. Esta limitación figura en los registros,
el manifest y la validación. No es una indisponibilidad de toda la sede.

## Unidad de registro y semántica

La extracción devuelve **1 instrumento auténtico con 24 enlaces documentales**.
Los planos, memoria y anuncios pertenecen al mismo POM: no se crean 24 proyectos.
Cada documento conserva su título, URL, página de procedencia y, cuando el rótulo
lo indica expresamente, fecha de publicación del boletín. No se infieren fechas
por la ruta de subida, «Noviembre 2025» o la fecha de creación de la ficha.

La corrección descargada confirma que el acuerdo de rectificación fue de
24-09-2026 y que el texto refundido se aprobó el 27-11-2025. Estas son fechas de
actos distintos y **no son la aprobación original del POM**. El parser de índices
no extrae el contenido PDF ni asigna esas fechas al registro; `fecha_acuerdo`,
`fecha_aprob`, `fecha_publicacion` general y `fecha` quedan vacíos. La publicación
se conserva por documento. El PDF rectificado sustituye al texto refundido
publicado anteriormente; se retienen ambos como trazabilidad histórica. No se
garantiza la vigencia de los planos de la página municipal.

No se extraen noticias, contratos, formularios ni licencias. Licencias, programación
y jitter están deshabilitados en el manifest. No hay geometría vectorial verificada,
coordenadas ni CRS asociados al instrumento; los planos PDF no se convierten en
polígonos. `geometry_status=unavailable`, `publication_ready=false`.

## Recorrido y fallos explícitos

Los dos índices cubiertos se leen completos; no tienen paginación en la captura
verificada. Las categorías visibles del POM son filtros de los planos ya incluidos
en la página. Si aparecen controles de paginación, el adaptador falla y exige
revisión: no acepta una primera página truncada. Las carpetas Wicket son exclusiones
de alcance documentadas, no páginas recorridas. Las pérdidas de encabezados,
documentos o anuncios y los nuevos documentos raíz no clasificables también fallan.
La actualización vuelve a leer ambos índices y sustituye la salida sólo después de
validar el resultado. IDs y agrupación permanecen estables; no usa un filtro temporal.

## Validación y evidencia local

Runtime requerido:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_cabanillas_del_campo -v`: **4 pruebas pasan**.
Cubren agrupación/deduplicación, procedencia, fechas, exclusión de formularios,
fallos por cambios/paginación, actualización, preservación de salida ante fallo,
licencias deshabilitadas y carga del manifest mediante el registro existente.

Extracción real con `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro / 24 documentos**.
`evidence/validation.json` registra `live_records`, `source_urls`, limitaciones,
resultado de pruebas y comprobaciones documentales. Los HTML de los dos índices
se capturan también durante la extracción con `config.evidence_dir`.

Se descargaron y verificaron cuatro PDFs genuinos (HTTP 200 y firma `%PDF-`):
memoria/normas de 2010 y los tres anuncios del texto refundido. La sede requiere
mantener la sesión HTTP entre ficha y visor; una petición aislada al visor devolvió
403, pero la descarga con sesión y Referer funcionó. Se conservan los enlaces
estables de ficha, sin persistir las URLs temporales de sesión como identificadores.
Los otros 20 planos se retienen como enlaces del inventario, sin verificar sus bytes.
Capturas PDF, hashes y tamaños están en `evidence/document-checks.json`; los extractos
de primeras páginas confirman el POM y los distintos actos de rectificación.

Toda la evidencia queda en `evidence/`, excluida del control de versiones. No se
modifican fuentes compartidas ni dependencias; no se ejecutan servicios de publicación.
