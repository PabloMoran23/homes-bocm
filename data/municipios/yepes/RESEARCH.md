# Yepes — Toledo — INE 45202

Verificación: 2026-11-09. Un adaptador municipal, sin dependencias nuevas.

## Descubrimiento e inventarios oficiales

Desde la navegación de https://www.yepes.es se llega a Concejalías → Urbanismo:
https://www.yepes.es/concejalia/urbanismo (HTTP 200).
Su bloque «Plan de ordenación municipal» publica dos fichas documentales:

- «Planos»: https://www.yepes.es/fileadmin/media/Ficheros_para_contenidos/Documentos_y_ficheros/Planos_Urbanismo.pdf
- «Normas urbanísticas»: https://www.yepes.es/fileadmin/media/Ficheros_para_contenidos/Documentos_y_ficheros/Normas_Urbanisticas.pdf

Ambos PDF devuelven HTTP 200 y cabecera PDF. Se han descargado completos.
La primera página del segundo identifica «PLAN DE ORDENACION MUNICIPAL DE YEPES
TOLEDO», «DOCUMENTO III. NORMAS URBANISTICAS»; sus pies mencionan 2006.
Esto acredita un instrumento real, no una solicitud, noticia ni anuncio de contratación.
El año impreso no se convierte en una fecha de aprobación. Los planos no ofrecen
texto útil con pdftotext; se conservan como documento gráfico, sin vectorizarlos.

Otros inventarios revisados (capturas HTML locales):

- https://www.yepes.es/ayuntamiento/documentos-y-tramites: solicitudes y declaraciones
  responsables, incluidas obra mayor/menor. Se excluyen; no acreditan concesiones.
- https://www.yepes.es/ayuntamiento/bandos: bandos generales y ordenanzas; no se
  convierten en proyectos de obras ni instrumentos urbanísticos individuales.
- https://yepes.sedelectronica.es/transparency/: enlazada desde la web municipal.
  HTTP 200, árbol Wicket con «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE (3)».
  La respuesta inicial sólo contiene la categoría y enlaces AJAX con token de sesión,
  no los títulos ni documentos de esos tres elementos. Ese árbol no se extrae y no
  se afirma cobertura de sus documentos. No se ha verificado un registro de licencias
  concedidas ni se han utilizado accesos privados.

## Semántica y cobertura

Una fila por instrumento: `yepes-proy-pom`; los dos documentos se agrupan en
`documentos`, con enlace de procedencia, título, URL, SHA-256 y tamaño descargado.
Los enlaces redundantes «Descargar PDF» no generan filas adicionales. Se descubren
las URLs en las fichas actuales, sin fijar documentos como semillas individuales.

Cada ficha muestra 18 junio 2021 (`datetime="18-06-2021"`). Se conserva exclusivamente
como `documentos[].fecha_publicacion`, especificando que es fecha municipal de
subida del documento. `fecha`, `fecha_publicacion` del instrumento, `fecha_acuerdo`,
`fecha_aprob` y `fase` permanecen nulos. No se ha contrastado un acuerdo ni la vigencia
consolidada del plan en boletines; su disponibilidad actual no demuestra ese estado.

Cobertura parcial: sólo este bloque documental del POM, no todo el histórico de
planeamiento, licencias, modificaciones, proyectos u obras públicas de Yepes.
No tiene paginación en la captura revisada. El adaptador rechaza indicadores de
paginación en vez de truncarlos. Si cambia la estructura, aparecen documentos de
identidad no revisada, falta una clase documental esperada o un enlace no devuelve
PDF, falla antes de sustituir la salida anterior. La actualización refresca el
inventario completo, sin cursor temporal ni pérdida de documentos por fecha.

## Geometría

`geometry_status: unavailable`. Se conservan planos PDF, pero no se ha verificado
geometría vectorial enlazable al instrumento. Latitud, longitud y geometría nulas;
`publication_ready: false`. No se asigna el centro municipal ni se inventan coordenadas.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_yepes -v`: 4 pruebas aprobadas. Cubren agrupación,
deduplicación de documentos, semántica de fechas, fechas ausentes, rechazo de
paginación/cambios de estructura/enlaces ajenos, resolución del manifest y contrato
de actualización, PDF inválido sin reemplazo de salida y licencias deshabilitadas.
Las pruebas usan fixtures sintéticos, sin depender de la red.

Extracción real mediante `load_portal_adapter(load_manifest('yepes'))` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro, 2 documentos**.
Para capturar las respuestas se estableció `adapter.config['evidence_dir']='evidence'`.
`evidence/validation.json` conserva conteo real, URLs, instante UTC, pruebas y límites.
`evidence/urbanismo.html`, ambos PDF y sus textos extraídos documentan la inspección;
las otras páginas revisadas también tienen captura. Evidencia local, fuera de los
cuatro archivos fuente entregables.

Manifest: `licencias.enabled=false`, `schedule.enabled=false`,
`geocode.jitter_missing=false`. Sin servicios de publicación, base de datos ni despliegue.
