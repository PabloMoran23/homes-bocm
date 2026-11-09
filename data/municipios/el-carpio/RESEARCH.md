# El Carpio (Córdoba), INE 14018

Investigación y extracción en vivo: 9 de noviembre de 2026. Se revisaron el contrato `municipio/adapters/portal.py`, el cargador de manifiestos y los ejemplos de Chipiona y Hernani antes de implementar este adaptador.

## Fuentes oficiales descubiertas

- Web municipal: https://ayunelcarpio.es/ y su API pública WordPress. La búsqueda de entradas `wp-json/wp/v2/posts?search=pgou&per_page=100` devuelve la ficha municipal de transparencia urbanística. La respuesta observada tenía `X-WP-TotalPages: 1`; la búsqueda de planeamiento confirmó la misma ficha. Estas búsquedas sirvieron para descubrir la fuente, no para construir un registro a partir del buscador.
- Inventario utilizado: https://ayunelcarpio.es/transparencia-en-materias-de-urbanismo-obras-publicas-y-medio-ambiente/ . Contiene enlaces de consulta genéricos a SITU@, un plan de emergencia y dos PDF específicos del PGOU. Es una página estática completa, sin paginación observada. El parser rechaza indicadores de paginación si aparecen, para no producir una extracción truncada.
- https://ayunelcarpio.es/urbanismo/ contiene impresos de solicitud; se excluye como registro de licencias concedidas.
- https://ayunelcarpio.es/areas_municipales/informacion-y-modelos-de-solicitudes/ contiene formularios y el PLID 2011–2016. No se incorpora a la cobertura de este adaptador, limitada al paquete documental del PGOU.
- Portal de transparencia actual, enlazado desde la portada: https://transparencia.ayunelcarpio.es/ . Se revisaron Publicidad activa y Planificación y evaluación. La ficha «Planes y Programas anuales y plurianuales…» no presentaba documentos utilizables en su HTML. No se genera ningún instrumento a partir de ese título genérico.

## Extracción y agrupación

Resultado vivo: **1 instrumento urbanístico real**, el Plan General de Ordenación Urbana de El Carpio, con **2 documentos** agrupados. No se convierten los dos anuncios relativos al mismo plan en dos proyectos. La identidad del registro es estable respecto al orden de enlaces y a duplicados. Se retienen el título de cada enlace, su URL y la página municipal de procedencia.

Documentos descargados y verificados durante la extracción:

1. https://ayunelcarpio.es/wp-content/uploads/2014/09/boja_no_41_de_02-03-2020.pdf . El inventario lo etiqueta como «Estudio de Impacto Ambiental Estratégico… (BOJA nº 41 de 02-03-2020». HTTP 200, `application/pdf`, firma `%PDF-`, 915294 bytes. PDF escaneado: `pdftotext` no produjo texto significativo. Se conserva la etiqueta del inventario sin afirmar que el archivo sea el estudio completo.
2. https://ayunelcarpio.es/wp-content/uploads/2014/09/anuncio_boja_pgou_27-1-2020.pdf . HTTP 200, `application/pdf`, firma `%PDF-`, 148768 bytes. El texto del anuncio municipal, firmado el 27 de enero de 2020, somete la adenda ambiental del PGOU a información pública y menciona una aprobación inicial del Pleno de 25 de febrero de 2014. Esto acredita un instrumento concreto y su tramitación histórica; no acredita aprobación definitiva ni vigencia actual.

La carpeta de subida `2014/09` no es una fecha de publicación documental. La fecha de firma del anuncio y la fecha de publicación en BOJA tienen significados distintos; se conservan sus etiquetas originales y **no se rellenan fechas de publicación, acuerdo o aprobación estructuradas**. La fecha del CMS tampoco se usa como fecha de acuerdo.

## Límites y semántica

Cobertura **parcial**, de documentación histórica que continúa publicada en una fuente oficial actual. No es el registro integral de planeamiento, obras o licencias, ni un inventario de instrumentos vigentes. No se consulta el registro interactivo SITU@ ni se crean proyectos desde sus enlaces genéricos. Se excluyen modelos, solicitudes, licitaciones, planes de emergencia y noticias ajenas a la cobertura. La regla se limita a anuncios ambientales del PGOU base: no absorbe documentos de modificaciones u otros instrumentos.

Sin coordenadas, geometría, fases o fechas inventadas. Cada registro declara `publication_ready: false` y `geometry_status: unavailable`. Licencias desactivadas por falta de un registro verificado de concesiones. El manifiesto identifica El Carpio de Córdoba, evitando los homónimos de Valladolid y Toledo, y fija `schedule.enabled: false`, `geocode.jitter_missing: false`, `licencias.enabled: false`.

La fuente respondió 403 con el agente HTTP predeterminado; las peticiones públicas con `User-Agent: Mozilla/5.0` respondieron 200. El adaptador utiliza ese encabezado y comprueba errores HTTP y redirecciones fuera del dominio municipal. Si desaparece el contenido o el paquete documental identificable, falla en lugar de generar un registro vacío o ficticio. `update_proyectos` refresca la página completa, sin simular un incremental mediante fechas.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_el_carpio -v
```

Seis pruebas correctas: agrupación y deduplicación, procedencia documental, exclusión de formularios/licitaciones/enlaces genéricos, rechazo de documentos externos, errores ante contenido vacío o cambiado y paginación, contrato de escritura/actualización y restricciones del manifiesto.

Extracción real mediante `load_manifest('el-carpio')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con captura opcional `portal.config.capture_dir = 'evidence'`. Se ejecutó también la anotación de política de entidades que añade el cargador compartido, sin modificarlo. La categoría queda como desconocida; no se fuerza una categoría de construcción para este instrumento.

Evidencia local, sin commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/inventory.html`, ambos PDF, capturas de descubrimiento y respuestas API. La validación contiene `live_records`, `source_urls`, limitaciones, metadatos HTTP y SHA-256 de los documentos. No se han usado bases de datos ni herramientas de publicación.
