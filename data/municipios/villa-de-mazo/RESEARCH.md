# Villa de Mazo — INE 38053

Investigación y extracción en vivo: 9 de noviembre de 2026. Municipio Villa de Mazo, provincia Santa Cruz de Tenerife, Canarias.

## Fuentes oficiales y alcance

Punto de descubrimiento municipal:
https://villademazo.com/el-ayuntamiento/gabinete-tecnico/

Esta página describe funciones del gabinete (incluidas licencias), pero no publica un registro de concesiones. Ninguna de esas funciones se convierte en expediente. Su enlace «Plan General de Ordenación» conduce actualmente a:
https://www.gobiernodecanarias.org/planificacionterritorial/materias/exposicion-de-planes-y-normas/ambito-municipal/planes-supletorios/pgos-villa-de-mazo-aprobacion-de-correccionesjulio-2026/

Es un expediente documental real mantenido por el Gobierno de Canarias y enlazado expresamente por el Ayuntamiento. Título extraído: «Aprobación de correcciones y nueva información pública del Plan General de Ordenación de la Villa de Mazo.» El scraper vuelve a descubrir el enlace municipal en cada ejecución; no devuelve un registro precargado ni fija una lista de documentos de julio. Conserva el título del expediente y todos los enlaces PDF/ZIP de su contenido documental: resolución, certificado, diligencia, índice y archivo comprimido del PGO. Son cinco documentos agrupados en **un instrumento**, no cinco proyectos distintos. Cada documento conserva título, URL y página de procedencia. La etiqueta de la resolución identifica el acuerdo de 24 de julio de 2026; no significa aprobación definitiva del PGO.

Inventarios adicionales inspeccionados, fuera del alcance de la extracción:

- Archivo autonómico: https://www3.gobiernodecanarias.org/aplicaciones/archivoplaneamientopt/pages/consulta/islaMunicipio.jsp?municipio=53&provincia=38 muestra 11 entradas de planeamiento general y 3 de desarrollo. No se navega ni se atribuye cobertura de ese archivo histórico, que utiliza navegación con estado de sesión.
- Índice IDECanarias: https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/LP/Mazo/863/indice.html contiene documentación de un PGO anterior. No se mezcla con la versión de correcciones de julio de 2026 ni se asume su vigencia.

La cobertura es deliberadamente parcial: únicamente el expediente del PGO enlazado actualmente por la web municipal. No es un inventario completo de actuaciones físicas, planeamiento histórico, expedientes privados o licencias. No se extraen anuncios de contratación, formularios ni noticias como proyectos.

## Semántica y fallos explícitos

El organismo custodio es el Gobierno de Canarias; `municipal_source_url` conserva la procedencia del enlace municipal, `inventory_url` la ficha autonómica y `documentos[].source_url` la procedencia de cada documento. `source: ayuntamiento` indica la vía de selección municipal y no atribuye al Ayuntamiento la autoría de los documentos autonómicos.

No se normalizan fechas: los títulos documentales conservan sus fechas explícitas. Una fecha de acuerdo de correcciones no se reutiliza como fecha de publicación ni como aprobación definitiva. No se deducen vigencia, ejecución, concesión ni coordenadas; `publication_ready: false` y `geometry_status: unavailable`. Las coordenadas de las oficinas que figuran en el pie de página autonómico no son geometría del proyecto.

La ficha observada es una página estática, sin paginación. Se recorren todos sus enlaces documentales, eliminando duplicados por URL. Si aparecen controles de paginación, falta el contenido, cambia el instrumento/municipio, desaparece el ZIP o cambia el dominio de procedencia, se produce un error antes de reemplazar la salida. Las actualizaciones vuelven a leer el expediente completo. No se descarga ni analiza el ZIP, y no se verifica internamente su contenido. `licencias.enabled`, `schedule.enabled` y `geocode.jitter_missing` están desactivados.

## Validación reproducible

Runtime autorizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_villa_de_mazo -v`

Cinco pruebas superadas: descubrimiento y ambigüedad, agrupación y metadatos, rechazo de fuentes vacías/cambiadas, detección de paginación y contrato del adaptador cargado desde el manifest. También se comprueba que un fallo no sustituye una salida válida y que las licencias no hacen peticiones.

Ejecución real mediante `load_portal_adapter(load_manifest('villa-de-mazo')).backfill_proyectos(...)`: **1 registro**, **5 documentos**. Los cuatro PDF devolvieron HTTP 200 y firma `%PDF`; solo se capturaron sus primeros 1024 bytes, sin descargar el archivo comprimido.

Evidencia local, no destinada al commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/municipal.html`, `evidence/dossier.html`, capturas exploratorias `discovery-*.html` y cuatro prefijos binarios `document-*.pdf.prefix`. El informe incluye recuento vivo, URLs, limitaciones y comprobaciones documentales. No se han utilizado bases de datos, publicación, despliegue ni geocodificación.
