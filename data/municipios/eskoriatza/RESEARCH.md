# Eskoriatza — INE 20034, Gipuzkoa

Verificación en vivo: 2026-11-09. Adaptador:
`municipio.adapters.eskoriatza:EskoriatzaAyuntamientoAdapter`.

## Descubrimiento y alcance

Se revisaron las fuentes oficiales:

- https://eskoriatza.eus/es/servicios/urbanismo/ — descripción del servicio y enlaces a trámites. Las solicitudes de licencia, enterados de obra y primeras utilizaciones **no son concesiones**; no se extraen.
- https://eskoriatza.eus/es/ayuntamiento/normativa/ — inventario municipal de normativa, con enlace al texto refundido de las NNSS. También contiene ordenanzas y planes administrativos ajenos al alcance. El Plan de Accesibilidad y su aprobación son otra fuente posible, fuera del catálogo implementado.
- https://eskoriatza.eus/es/ayuntamiento/normativa/normas-subsidiarias/ — catálogo implementado: texto refundido y enlaces a sus modificaciones puntuales.
- https://eskoriatza.eus/es/ayuntamiento/normativa/normas-subsidiarias/sorautz/ — detalle descubierto desde el catálogo.
- https://eskoriatza.eus/es/ayuntamiento/normativa/normas-subsidiarias/santa-ana/ — detalle descubierto desde el catálogo.

Todos los HTML anteriores respondieron HTTP 200 y están capturados en `evidence/`.
Se usa exclusivamente `#content .c1`, evitando navegación lateral, pie y traducciones.
Los detalles se descubren desde el inventario en cada ejecución, sin fijar una lista
cerrada de noticias o limitar el número de registros. No hay paginación en estas
páginas estáticas. Si aparecen controles de paginación, enlaces de contenido no
soportados o enlaces a niveles adicionales, falla expresamente: no se acepta una
instantánea truncada.

## Resultado real y agrupación

La extracción mediante el adaptador produjo **3 instrumentos**:

1. Texto Refundido de las Normas Subsidiarias de Planeamiento de Eskoriatza: un PDF municipal del boletín.
2. Modificación puntual en Sorautz: **40 enlaces documentales**, agrupados en un registro: dos memorias, diez planos provisionales, diez definitivos, seis detalles, diez planos informativos y dos acuerdos. Se conserva la errata «Mocificación» del título del inventario.
3. Modificación puntual en Santa Ana: el detalle enumera memoria y planos como texto sin hipervínculos. Se conserva el instrumento identificado por el inventario y su página, con `documentos=[]` y `documentacion_status=sin_enlaces_documentales`; no se inventan URLs.

Los IDs derivan de la URL canónica del instrumento y no cambian al añadir documentos.
Cada documento conserva título, sección, URL original publicada, URL con HTTPS
para el host municipal y página de procedencia. Los planos provisionales y definitivos
pertenecen al mismo instrumento; sus rótulos no se convierten en fases del expediente.

La descripción conserva el contenido de la página, sin inferir estado de ejecución.
No se afirma que este catálogo histórico refleje todo el planeamiento vigente ni
que estas actuaciones estén en obras. No se extraen noticias, licitaciones, formularios,
licencias concedidas, presupuestos ni planes administrativos generales.

## Fechas y documentos

El relato del catálogo cita la sesión del Consejo de Diputados del **23 de julio de
2002**: se guarda únicamente como `fecha_acuerdo` del texto refundido. No se equipara
a fecha de aprobación ni de publicación. En la página de Normativa se etiqueta
BOG 01/10/2002, pero esa fuente queda como descubrimiento y no se incorpora al
parser: `fecha_publicacion` sigue siendo nula. Las fechas de Sorautz y Santa Ana
son nulas. Las rutas de boletines, directorios de subida y metadatos WordPress no
se usan para deducir fechas de acuerdos o aprobaciones.

Comprobaciones documentales independientes de muestra:

- https://eskoriatza.eus/wp-content/uploads/2013/07/b021001-185i.pdf — HTTP 200, application/pdf; captura local.
- https://eskoriatza.eus/wp-content/uploads/2013/11/Arau-Aldaketa-Dokumentua_Memoria1.pdf — HTTP 200, application/pdf; captura local.
- https://ssl4.gipuzkoa.net/castell/bog/2012/01/31/c1200904.pdf — ConnectTimeout; enlace histórico conservado como publicado, sin garantizar accesibilidad.

No se han descargado ni interpretado exhaustivamente todos los PDFs. El adaptador
extrae enlaces publicados, no certifica disponibilidad ni contenido de cada archivo.

## Geometría y límites

`geometry_status: unavailable`. No hay geometrías vectoriales asociadas a instrumentos
en el HTML revisado; los planos PDF no se vectorizan. No se verificó una unión con
cartografía externa. `lat`, `lon` y `geometry` son nulos y `publication_ready=false`.
No se inventan coordenadas, centroides, CRS ni fechas.

Cobertura parcial: este catálogo municipal concreto, no un registro integral de obras,
planeamiento ni licencias. Santa Ana carece de descargas. Sorautz conserva enlaces
antiguos a acuerdos que pueden no ser accesibles. La actualización vuelve a leer
la instantánea completa del catálogo, sin filtros temporales ni estado incremental.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_eskoriatza -v`: **7 pruebas**, correctas. Cubren agrupación/deduplicación, procedencia documental, fechas explícitas frente a rutas, documentos sin enlaces, rechazo de paginación/cambios de contenido, recorrido de detalles, preservación del resultado ante fallo y manifest.
- Extracción real: `EskoriatzaAyuntamientoAdapter('eskoriatza', {'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **3 registros**, 41 enlaces documentales.
- Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`, cinco capturas HTML y dos PDF de muestra. Las pruebas usan fixtures sintéticos incluidos en el archivo de tests, sin depender de las capturas ni de la red.

El manifest deshabilita licencias, programación y jitter. Sin cambios de dependencias,
fuentes compartidas, publicación ni servicios externos de datos. La evidencia no forma
parte de los cuatro archivos fuente entregables.
