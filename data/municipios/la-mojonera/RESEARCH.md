# La Mojonera — Almería — INE 04903

Investigación y extracción real: 8 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y alcance

Se examinó el [inventario municipal de planeamiento](https://www.lamojonera.es/Servicios/cmsdipro/index.nsf/informacion.xsp?documentId=10EDD3F85EE5EA06C12581360022A140&p=LaMojonera).
El índice accesible mediante consulta web enumera documentos del PGOU, adaptación
parcial y modificaciones. Las peticiones directas desde Python al portal municipal
y su alojamiento provincial devuelven HTTP 200 con un control JavaScript/CAPTCHA,
no el inventario. `evidence/inventory.html` captura esa respuesta. No se utilizan
los resultados del buscador como registros ni como respaldo precargado.

La fuente operativa es el [inventario público de resoluciones de evaluación
ambiental estratégica de la Junta de Andalucía](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions).
Su formulario ofrece `find=findResolucionesFiltered` y `filter5` para municipio.
La [consulta municipal exacta utilizada](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/find?find=findResolucionesFiltered&filter5=MOJONERA&page=1&size=10)
retorna seis fichas, con provincia ALMERÍA y municipio MOJONERA (LA) comprobados
por el parser tanto en el listado como en los detalles. El código INE se fija
como identidad del municipio solicitado, no se deduce del CIF municipal.

La extracción produce cuatro registros reales agrupados por expediente ambiental:

| Instrumento identificado por la fuente | Expediente | Fichas | Documentos enlazados |
| --- | --- | ---: | ---: |
| Innovación nº 7 del PGOU | EAE/AL/011/17 | 7708 | 3 |
| Modificación puntual nº 10 del PGOU | EAE/AL/001/22 | 34040 | 3 |
| Innovación nº 11 del PGOU | EAE/AL/023/23 | 41400, 44381, 44380 | 4 |
| Plan Parcial de Ordenación del Sector 22 | EAE/AL/027/25 | 52841 | 1 |

Cada ficha se consulta en `/medioambiente/daepu/resolucions/{id}`. Los títulos
conservan la denominación literal de la actuación ambiental, que identifica el
instrumento urbanístico. No se generan actuaciones a partir de formularios,
licitaciones o noticias. El identificador estable deriva del expediente, sin
los paréntesis variables ni el `jsessionid` temporal. Se conservan todas las
fichas y los once enlaces documentales, incluidos los dos informes de la
innovación 11 publicados en fichas distintas. No se deduplican documentos por
el título o la fecha, pues sus enlaces son distintos.

La página observada declara «Página 1 de 1». El adaptador sigue todas las páginas
según esa metainformación; si falta, se repite una ficha, cambia el número de
páginas o falla cualquier detalle, aborta sin reemplazar el resultado previo.
Las pruebas simulan también un inventario de dos páginas. No hay límite de
páginas que trunque silenciosamente la consulta.

Se comprobó además el [anuncio municipal del Sector 22 en BOJA](https://www.juntadeandalucia.es/boja/2026/188/60),
publicado el 28/09/2026, que indica acuerdo de aprobación inicial del 15/09/2026.
Es una comprobación contextual, capturada en `evidence/boja-sector22.html`; no es
una segunda fuente integrada ni se trasladan esas fechas a la resolución
ambiental del 03/03/2026. El inventario ambiental no refleja necesariamente la
fase urbanística actual del plan.

## Semántica y limitaciones

Cobertura **parcial**, limitada a instrumentos municipales presentes en el
inventario ambiental autonómico. No es un histórico completo del PGOU, registro
de obras públicas ni inventario de licencias concedidas. La fuente real de los
registros es `junta_andalucia`; el valor de manifest `source: ayuntamiento` es
la ruta existente del pipeline para adaptadores municipales, no una atribución
del alojamiento autonómico al Ayuntamiento.

`fecha_resolucion_ambiental` se conserva por ficha/documento. La tabla de detalle
llama genéricamente a la columna «Fecha de Resolución»: su valor literal queda
en `fecha_resolucion_fuente`. Para documentos de tipo «Publicación en BOJA (PB)»
se representa como `fecha_publicacion`, y para los demás como
`fecha_resolucion_ambiental`. Nunca se convierte en fecha de aprobación del plan.
La innovación 11 contiene fechas ambientales diferentes (29/07/2024 y
02/08/2024); se mantienen asociadas a sus fichas/documentos sin conciliarlas ni
inventar una fecha global. No se analizan jurídicamente los PDFs para afirmar
concesiones, aprobación definitiva o vigencia. Sin fase global inferida, sin
coordenadas y con `publication_ready: false` y `geometry_status: unavailable`.

Licencias, programación y jitter desactivados en el manifest. La actualización
vuelve a consultar el inventario completo; no usa una marca temporal para
omitir fichas o perder documentos incorporados después.

## Validación reproducible

- Parser: `python -m unittest municipio.test_la_mojonera -v`, siete pruebas.
  Verifican identidad territorial, enlaces sin sesión, separación de fechas,
  agrupación sin contaminación documental, rechazo de contenido inválido,
  paginación completa y preservación del resultado ante un fallo.
- Extracción real mediante `load_manifest`, `load_portal_adapter` y
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
  `manifest.portal.config['capture_dir'] = 'evidence/live'`.
- Resultado: cuatro instrumentos, seis fichas, once documentos. Las capturas
  del listado y de todos los detalles quedan en `evidence/live/`.
- `evidence/validation.json` registra recuento, URLs consultadas, limitaciones,
  pruebas y verificación de un PDF documental real. La muestra de la ficha
  34040 respondió HTTP 200, 216068 bytes, cabecera MIME
  `application/octet-stream;charset=UTF-8` y firma `%PDF-` válida; guardada en
  `evidence/sample-document.pdf`. El resto de enlaces documentales se extrae
  de los detalles oficiales, sin afirmar haber descargado todos sus PDFs.

Evidencia local, excluida del commit. Sin instalación, bases de datos,
publicación, despliegue ni cambios en fuentes compartidas.
