# Chantada — INE 27016, Lugo, Galicia

Investigación y extracción en vivo: 2026-11-08. Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuentes oficiales

- Urbanismo municipal: https://www.concellodechantada.org/servizos/urbanismo/
- Ficha municipal del PXOU: https://www.concellodechantada.org/servizos/urbanismo/plan-xeral-de-ordenacion-urbanistica/
- Inventario actual: https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=27016
- Resumen regional: https://siotuga.xunta.gal/siotuga/urb (fila 27016, Chantada, PXOU, 1985-07-29).

La ficha municipal identifica el PXOU y enlaza al inventario de SIOTUGA. El enlace municipal todavía usa `http://www.planeamentourbanistico.xunta.es/siotuga/inventario.php?inv=1&idconcello=27016`. La prueba HTTPS de ese dominio antiguo falla por certificado. Se usa el dominio actual oficial `siotuga.xunta.gal`, con verificación TLS activa. El scraper exige que la página municipal siga enlazando SIOTUGA para 27016.

El HTML de SIOTUGA ofrece un formulario público anónimo. Su JavaScript `https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js?2.5.0` documenta estas consultas de lectura:

1. POST `https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php`: `id=27016`, `idclase=14,13,16,18` (una petición por categoría). Son planeamiento general, desarrollo, histórico y delimitaciones rurales.
2. POST `https://siotuga.xunta.gal/siotuga/assets/inventario/getIOTPU.php`: `iddoc=<id>`, `idp=0`, `lang=gl_ES`.

Ambas usan el nonce del formulario público, obtenido de nuevo en cada ejecución, sin autenticación. No se consulta ningún registro privado. Cada respuesta de inventario es un array completo; DataTables aplica paginación en el navegador. Se recorre todo el array de las cuatro categorías, sin límites de filas, páginas ni filtros temporales. Una respuesta con envoltorio/paginación desconocida provoca error. Las categorías vacías usan JSON `null`. Si todas quedan vacías, falla la extracción. Los detalles deben coincidir en ID, municipio y fechas y ofrecer documentos bajo el repositorio CHANTADA.

## Resultado y unidad de registro

**17 instrumentos reales y 251 enlaces documentales**, agrupados por ID SIOTUGA. Categoría 14: 12 instrumentos. Categoría 13: 5. Categorías 16 y 18: vacías en esta ejecución. Los 47 documentos del plan general de 1985 forman un único registro; los 10 documentos de la modificación número 8 forman otro. Se incluyen también Alemparte/Mariz, Esmoriz, Portada/Santo Estevo, Praza de Galicia, Rúa do Rego, piscinas, modificación número 1, N-540/campo de fútbol, ordenanza 7, SUP-2/SUNP-1, ampliación de Os Acibros, SUNP-3, plan parcial industrial, Os Pilos y la modificación del PP SUP-2 de conexión con Os Acivros. Los títulos conservan la grafía del inventario.

Cada registro contiene ID estable, URL del inventario, ID y parámetros de consulta de la ficha, organismo documental (Xunta), categorías y todos los documentos, con títulos y grupos originales. No se genera un registro por plano, formulario ni anuncio de contratación. Los duplicados de un instrumento se agrupan por ID; enlaces repetidos se agrupan por URL conservando los nombres de grupos. Las modificaciones siguen siendo instrumentos distintos del plan matriz. El detalle se recorre completo antes de escribir el snapshot atómicamente. `update_proyectos` vuelve a extraer el inventario completo.

La comprobación de documentos leyó los primeros 1.024 bytes de tres enlaces: memoria del PXOU 24329 y memoria de la MP 28553, ambos HTTP 200, `application/pdf` y firma `%PDF-`; plano del instrumento 26700, HTTP 200 e `image/jpeg`. No se descargaron ni se verificaron individualmente los 251 archivos completos.

## Fechas, procedencia y límites

`fechaaddef` se conserva como `fecha_aprob`. `fechabop`, `fechadog` y `fechanormativabop` se conservan en campos explícitos de publicación BOP, DOG y normativa BOP. No se infiere fecha de acuerdo ni se usa una fecha genérica. No se confunden fechas del CMS, del acuerdo o del boletín. El registro 28649 presenta aprobación 2016-03-09, DOG 2013-05-27 y BOP/normativa 2024-05-21: se preserva esa discrepancia de la fuente, sin intentar corregirla. La fecha de 1985 mostrada entre paréntesis por el ayuntamiento no se interpreta por sí sola como aprobación; la etiqueta del endpoint sí identifica aprobación definitiva.

La inclusión en el inventario no garantiza vigencia jurídica individual ni ejecución física. Se retienen las incidencias jurídicas del detalle. No se asignan fases, coordenadas, geometrías ni centros municipales; `publication_ready=false`, `geometry_status=unavailable`. `licencias.enabled=false`, `schedule.enabled=false` y `geocode.jitter_missing=false`.

Cobertura parcial: exclusivamente los cuatro grupos de planeamiento municipal de SIOTUGA. No es un censo de proyectos, obras o licencias de Chantada. El inventario territorial `assets/iot/queryIotInv.php` fue inspeccionado durante la investigación pero se excluye de este adapter (incluye instrumentos de ámbito supramunicipal). Tampoco se incorpora el inventario de evaluación ambiental `https://medioambiente.xunta.gal/en-curso`, que contiene otros expedientes, como el PXOM en tramitación y la MP 11; la MP 12 aparece en publicaciones ambientales de 2026. Esas publicaciones no son aprobaciones urbanísticas. Noticias municipales de obras y el Plan Municipal de Obras 2026 se detectaron en la navegación, pero no forman parte de esta cobertura. Los modelos de solicitud de licencia y la sede electrónica no son un registro de licencias concedidas y se excluyen.

## Verificación reproducible y evidencia local

Pruebas offline: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_chantada -v` — 7 pruebas correctas. Cubren agrupación/aislamiento documental, identidad, separación de fechas, categorías vacías, cambios de esquema/paginación, duplicados, fechas inválidas, municipio/repositorio incorrectos, falta de documentos, carga del manifiesto y licencias desactivadas sin red.

Extracción real: instancia de `ChantadaAyuntamientoAdapter('chantada', {'evidence_dir': '<workspace>/evidence'})`, llamada a `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. No se ejecuta publicación, base de datos ni geocodificación. `evidence/validation.json` contiene resultado, URLs, conteo y limitaciones. `evidence/` conserva HTML municipal y del inventario, JSON de las cuatro categorías y 17 detalles, controles JavaScript y muestras documentales. La evidencia es local y no forma parte de los cuatro archivos fuente.
