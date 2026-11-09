# Iniesta (Cuenca), INE 16113

Investigación y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales descubiertas

- Web municipal: https://www.iniesta.es/ . El pie identifica Iniesta, Cuenca, Plaza Mayor 1, 16235. No confundir con Graja de Iniesta o Castillejo de Iniesta.
- Inventario temático de noticias del POM: https://www.iniesta.es/tag/plan-de-ordenacion-municipal/ . Se utilizó para descubrimiento, no como registro de proyectos genéricos.
- Aviso municipal del 27 de mayo de 2026: https://www.iniesta.es/2026/05/27/ayuntamiento-somete-informacion-publica-plan-ordenacion-municipal/ . Identifica el POM y remite a la ruta 7 / 7.1 / POM en la sede. Corrige el plazo anunciado: 6 de julio, no 11 de junio. No se deduce vigencia actual del plazo.
- Portal actual: https://iniesta.sedelectronica.es/transparency . El enlace antiguo `/info.0` abre hoy el inicio con un catálogo de solicitudes, no el inventario documental. La solicitud de licencia urbanística no es una concesión y no se extrae.
- Urbanismo: https://iniesta.sedelectronica.es/transparency/9e6e5ed4-f923-4fdc-a796-ef37547a3c0d/ . Presenta las secciones 7.1 planeamiento (9 documentos), 7.2 medioambiente (0), 7.3 normativa (0), 7.4 obras e infraestructuras (32) y 7.5 indicadores (0). La sección 7.4 queda fuera de esta implementación: no se ha clasificado su contenido como actuaciones materiales.
- **Inventario de extracción**: https://iniesta.sedelectronica.es/transparency/bef8cbc5-581e-4c0b-8163-aaa156086a1c/ . Dos carpetas de instrumentos; la modificación de NN.SS. para centro de mayores anuncia 0 documentos y está efectivamente vacía. Se registra como omitida, sin convertir una carpeta vacía en proyecto.
- POM: https://iniesta.sedelectronica.es/transparency/c50ae90f-dab1-47bd-9e95-d3580d1a85eb/ . Nueve documentos: anuncio de exposición, planos de ordenación, normas urbanísticas, memoria informativa, catálogo de bienes y espacios protegidos, planos de información, memoria justificativa, informe de sostenibilidad medioambiental y catálogo de suelo residencial público.

## Extracción y semántica

Resultado vivo: **1 instrumento con 9 enlaces documentales**, no nueve proyectos. Se recorre la tabla `TransparencyListPanel` de 7.1, se resuelven las acciones Wicket con una sesión HTTP y su cabecera `Ajax-Location`, y se visita cada carpeta. Los enlaces `/preview-document/UUID` se conservan sin fijar tokens de descarga temporales. El ID del instrumento deriva de su carpeta estable. No hay expedientes ni documentos precargados en el adaptador.

No se observó paginación en 7.1 ni en sus dos carpetas. El parser rechaza controles de continuación/paginación, exige que la cantidad de documentos únicos coincida con la anunciada, rechaza carpetas anidadas y entradas desconocidas, y falla ante una tabla ausente o la desaparición de los instrumentos documentados. No exporta silenciosamente la primera página. La actualización vuelve a leer el inventario completo; no es un incremental por fecha ni un histórico de documentos retirados.

El anuncio se comprobó además descargando su PDF desde la vista oficial:
https://iniesta.sedelectronica.es/preview-document/17b48887-3e8e-4f7e-a5b1-70b69dccaf0b . HTTP 200, `application/pdf`, 230231 bytes y firma `%PDF-`. El documento es una copia del DOCM, año XLV, núm. 79, página 15168, de **28 de abril de 2026**, referencia 2026/2900. El anuncio está fechado el **15 de abril de 2026** y cita el Decreto de Alcaldía 127/2026 de **8 de abril de 2026**, que acuerda la exposición pública del POM e ISA. Son tres fechas con significado distinto; ninguna acredita aprobación definitiva. La fecha de creación de la ficha de sede tampoco equivale a un acuerdo.

El parser no lee automáticamente el contenido PDF: por ello los registros omiten fechas y fase, en lugar de copiar esta comprobación manual como dato constante. La publicación documental no prueba vigencia del instrumento, concesión de licencia o ejecución de una obra. No se generan coordenadas. `publication_ready=false`, `geometry_status=unavailable`; schedule, jitter y licencias desactivados en el manifest.

## Validación y evidencia local

Se ejecutaron `python -m unittest municipio.test_iniesta -v` (6 pruebas correctas) y una llamada real a `backfill_proyectos` cargando el manifest mediante `load_portal_adapter`, incluida la política compartida de entidades. Las pruebas cubren agrupación documental, exclusión de formularios/licitaciones, ausencia de fechas/geometría inventadas, paginación, errores de estructura, dominios externos, navegación Wicket, carpeta vacía y discrepancia de cantidades. Una extracción fallida no sustituye el archivo anterior.

Evidencia local no destinada a commit:

- `evidence/proyectos.jsonl`: salida real (1 registro, 9 documentos).
- `evidence/validation.json`: conteo, URLs consultadas, limitaciones, carpeta omitida y resultado de política de entidades.
- `evidence/live-captures/`: respuestas HTML y metadatos HTTP de la ejecución real, incluidas las acciones Wicket.
- `evidence/folder-*.html`, `evidence/transparency-root.html`, aviso municipal y otras capturas de descubrimiento.
- `evidence/pom-public-notice.pdf` y `.txt`: anuncio oficial verificado y texto extraído con `pdftotext` preinstalado.

Cobertura deliberadamente parcial: inventario documental actual de planeamiento 7.1, sin registro público verificado de licencias, sin barrido de contratación o noticias generales, sin inventario de obras 7.4, sin garantía de exhaustividad histórica. No se han utilizado servicios de publicación, bases de datos ni despliegue.
