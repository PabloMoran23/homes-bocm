# Benahadux — INE 04024, Almería

Investigación y extracción en vivo: 9 de noviembre de 2026.

## Inventario oficial elegido

La web municipal actual, https://www.benahadux.es/, presenta el bloque
«Obras en curso y proyectos en ejecución» (`.view-obras-en-curso`). Contiene
fichas del tipo Drupal `obras-y-proyectos`, con enlace de regreso a la portada:

- https://www.benahadux.es/obras/pabellon-de-deportes-de-benahadux
- https://www.benahadux.es/obras/residencia-para-personas-mayores-en-benahadux

Son actuaciones físicas concretas, no anuncios de licitación convertidos en
proyectos. La primera describe el proyecto básico de un pabellón en las parcelas
ED y ES de UA-14 y la preparación del proyecto de ejecución. La segunda describe
una residencia en Calle Ceuta s/n. Se conservan título, estado literal, extracto,
descripción, fecha de inicio y documentos de cada ficha. Resultado real: **2 obras**.

El scraper descubre los enlaces en el bloque y visita las fichas; no devuelve una
lista de obras precargada. Cada ficha produce un registro estable por URL. Los PDF
se agrupan y deduplican dentro de ese registro, conservando título de enlace y URL
de procedencia; documentos de otras partes de la página no se incorporan.

PDF vinculados:

- https://www.benahadux.es/sites/default/files/2026-07/MEM.%20DESC-PB-PABELL%C3%93N%20EN%20BENAHADUX.pdf
- https://www.benahadux.es/sites/default/files/2026-08/DATOS%20RESIDENCIA_0.pdf

Ambos respondieron HTTP 200, `application/pdf`, con firma `%PDF-` comprobada.
Solo se capturaron sus primeros 4096 bytes; no se interpretó el contenido completo
como prueba de aprobación administrativa.

## Descubrimiento y límites

También se consultó el portal municipal anterior alojado por Diputación:
https://www.dipalme.org/Servicios/cmsdipro/index.nsf/index.xsp?p=Benahadux.
Enlaza la sede electrónica y apartados PGOU/Normas Subsidiarias. La web actual
también enlaza estos apartados oficiales:

- https://benahadux.sedelectronica.es/transparency/5c302abd-9b12-4af7-af16-91999dc520fd/
- https://benahadux.sedelectronica.es/transparency/5b747bb4-3e8f-475d-9647-2789632a86f9/

El segundo presenta «Mostrar más» para documentos. Estos apartados no forman
parte del alcance implementado: no se afirma haber recorrido todo el planeamiento
ni se devuelve cada anexo como instrumento independiente. Tampoco se incluyen
noticias, formularios, contratación, inventario patrimonial ni registro de licencias.

La cobertura es **parcial**, limitada al bloque actual de obras de portada, que
podría ser una selección editorial. No es un histórico municipal exhaustivo. No
se observó paginación en ese bloque: el carrusel contiene las dos tarjetas en HTML,
y sus controles solo cambian la tarjeta visible. El adapter recorre enlaces de
paginación explícitos si aparecen, deduplica fichas entre páginas y rechaza
controles dinámicos reconocidos o ciclos de más de 100 páginas nuevas, sin escribir
una salida truncada. El refresco incremental es una nueva instantánea completa
de esta cobertura; no mantiene historial de actuaciones retiradas.

## Semántica

`fecha_inicio` procede exclusivamente del campo rotulado «Fecha de inicio»:
2026-08-01 para el pabellón y 2026-06-23 para la residencia. No implica que una obra
planificada haya empezado materialmente. `fase` conserva el estado municipal
literal: «Planificado» y «En Ejecución», respectivamente. Las fichas no proporcionan
fechas de acuerdo, aprobación ni publicación verificadas; esas fechas quedan nulas.
Las carpetas fechadas de archivos, el reloj de la sede y las fechas de noticias no
se usan para rellenarlas. La mención de aprobación del proyecto básico se conserva
en el texto sin inventar fecha ni licencia concedida.

No se interpretan los widgets cartográficos como geometría verificada de las obras;
no se emiten coordenadas ni se realiza geocodificación. `publication_ready: false`.
Manifest: municipio y provincia exactos, `schedule.enabled: false`,
`geocode.jitter_missing: false`, `licencias.enabled: false`.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_benahadux -v`: cinco pruebas correctas.
Prueban agrupación y aislamiento de documentos, semántica de fechas, rechazo de
páginas genéricas, recorrido de paginación con deduplicación, rechazo de carga
dinámica/enlaces externos y licencias desactivadas.

Se cargó el manifest con `municipio.manifest.load_manifest('benahadux')` y se ejecutó
`BenahaduxAyuntamientoAdapter(...).backfill_proyectos(Path('evidence/proyectos.jsonl'))`
contra la web real, con `config={'evidence_dir': 'evidence'}` para capturas HTML.
Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`, HTML de
portada y fichas, y prefijos PDF. La validación incluye `live_records: 2`, fuentes,
limitaciones y comprobaciones documentales. No se ejecutaron procesos de publicación,
base de datos, geocodificación o despliegue. La evidencia no se añade como fuente.
