# Azpeitia — Gipuzkoa — INE 20018

Verificación: 2026-11-07. Adaptador `AzpeitiaAyuntamientoAdapter`.

## Fuente oficial y descubrimiento

El portal municipal https://www.azpeitia.eus/ enlaza «Hirigintza plangintza»:
https://www.azpeitia.eus/udala/hirigintza-plangintza . Es un inventario municipal
actual, no una noticia elegida como proyecto ni un anuncio de contratación.
Se revisaron sus cuatro bloques: plan general, primera modificación, planeamiento
de desarrollo y gestión urbanística. Los dos últimos reúnen instrumentos antiguos
mediante páginas de detalle y expedientes recientes con PDFs directamente anidados.
La página se sirve completa por HTTP, sin paginación observada ni carga adicional
necesaria para desplegar los acordeones.

## Cobertura implementada

Cobertura **parcial y explícita**: todas las entradas de desarrollo y gestión que
identifican en su propio título un expediente `AAAA PLAN NNNN` (sin espacios en la
fuente), un plan especial, estudio de detalle, proyecto de urbanización o proyecto
de reparcelación y sus documentos PDF oficiales. Se descubren en cada ejecución;
no hay una lista fija de expedientes ni límite de registros.

La extracción real produjo **6 instrumentos y 23 enlaces documentales**:

| Expediente | Instrumento |
| --- | --- |
| 2024PLAN0010 | Plan especial de ordenación urbana |
| 2025PLAN0017 | Reparcelación UE.1/31 Trukutxo |
| 2025PLAN0018 | Urbanización 31 Trukutxo |
| 2025PLAN0021 | Reparcelación Anardi 32, AD-32.1, B10.32.1 |
| 2026PLAN0001 | Estudio de detalle Arana 2-4-6-8-10-12 |
| 2026PLAN0031 | Estudio de detalle 4.1 Santutxo y 1.2 Done Jakue 3 |

Los documentos, traducciones, publicaciones GAO y certificados de un expediente
forman un único registro. Se deduplican por URL documental y se conservan el título
original, número, enlaces, etiquetas documentales, página de procedencia y secciones.
El ID depende del expediente y no del orden, fecha de consulta o documento principal.
Los proyectos de urbanización y reparcelación de Trukutxo son instrumentos distintos.

Quedan fuera el PGOU y su primera modificación, las entradas históricas sin número
explícito en el título, convenios urbanísticos (incluido 2025PLAN0023), formularios,
solicitudes y noticias. No se afirma cobertura completa del planeamiento municipal,
de obras públicas ni de todos los expedientes históricos. No se siguen las páginas
de detalle antiguas. No se ha verificado un registro de licencias concedidas:
`licencias.enabled: false` y ambos métodos de licencias producen cero registros.

## Semántica, fechas y geometría

La fase de aprobación definitiva solo se atribuye si el título del instrumento
contiene esa afirmación expresa en euskera. La ubicación bajo «Tramitean» o
«Ebatzita» se conserva como contexto de inventario, sin convertirla en acuerdo.
No se interpreta el año del expediente ni la fecha de consulta como fecha de
publicación o aprobación. Los PDFs no se analizan para obtener fechas, por lo que
`fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` son nulos. Los enlaces
a anuncios y certificados conservan la posibilidad de verificarlas posteriormente.

`geometry_status: unavailable`. El inventario seleccionado enlaza documentos, sin
geometría verificable asociada a estos expedientes. No se han georreferenciado planos
PDF ni buscado correspondencias por nombre en capas GIS externas. Coordenadas y
geometría nulas, `publication_ready: false`, `geocode.jitter_missing: false`.
La preparación para revisión del scraper no implica preparación para publicar mapas.

## Validación y funcionamiento

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_azpeitia -v
```

Cuatro pruebas verifican agrupación entre secciones, deduplicación y procedencia,
fechas desconocidas, exclusión de convenios/formularios/entradas sin expediente,
fase explícita, rechazo de paginación, ausencia de documentos y cambios de contenido,
preservación del resultado anterior ante fallo de red y licencias deshabilitadas.

La extracción real se ejecutó mediante `load_manifest('azpeitia')`,
`load_portal_adapter(manifest)` y `backfill_proyectos`, con anotación de la política
compartida: seis expedientes, cero entidades desconocidas. Evidencias locales:
`evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/inventory.html`
y PDFs principales por expediente. La validación enumera todos los enlaces y las
comprobaciones HTTP. Se descargó un PDF principal por instrumento; los otros 17
enlaces se conservan sin afirmar verificación de su contenido o disponibilidad.

Las actualizaciones refrescan la instantánea completa; no constituyen un histórico
de eventos ni un mecanismo de bajas. Si aparecen controles de paginación, faltan
secciones, no hay instrumentos soportados, faltan PDFs o existe ambigüedad de tipo
o expediente, la extracción falla explícitamente antes de reemplazar el resultado.
No se inventa una instantánea vacía. Escritura atómica tras análisis satisfactorio;
timeout de red de 40 segundos. `schedule.enabled: false`.
