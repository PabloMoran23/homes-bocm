# Sariñena — INE 22213, Huesca, Aragón

Verificación en vivo: 2026-11-09. Un único adaptador municipal, con fuente
documental oficial autonómica. Cobertura parcial: inventario histórico de
planeamiento SIUa, no registro de licencias concedidas ni inventario completo de
obras. `schedule.enabled=false`, `geocode.jitter_missing=false`,
`licencias.enabled=false`; todos los registros tienen `publication_ready=false`.

## Fuentes descubiertas y comprobadas

- [Archivo de planeamiento SIUa de Sariñena](https://idearagon.aragon.es/archivoSIUa/?CMUNIINE=22213):
  HTTP 200. La respuesta identifica explícitamente el municipio SARIÑENA y el
  código 22213. Incluye 30 filas de tramitación de 19 expedientes distintos:
  PGOU, texto refundido, rectificaciones, modificaciones y dos planes parciales.
  La fila más reciente visible es la modificación 12, expediente
  CPU-22/2024/48, acuerdo 23/07/2024, publicación 29/07/2024. La página sigue
  disponible hoy, pero su contenido no garantiza actualización completa.
- [Detalle de la modificación 12](https://idearagon.aragon.es/archivoSIUa/?CODEXP=CPU-22/2024/48&FASE=4&TITULO=MPGOU):
  HTTP 200. Declara el documento `MA12 PGOU SARIÑENA TR.pdf`, identificador
  documental `0906fca30c74590c`. Los detalles presentan sus documentos en
  declaraciones JavaScript `addDoc`; se leen como datos sin ejecutar código.
  Se consultaron los 19 detalles, sin recorte de documentos. Se conservaron
  198 documentos del repositorio, además de enlaces a acuerdos y boletines.
- [Sistema de Información Urbanística de Aragón](https://www.aragon.es/es/urbanismo-y-ordenacion-del-territorio/siua):
  página institucional que identifica SIUa como herramienta oficial del Gobierno
  de Aragón para difundir documentos de planeamiento. La nueva interfaz
  [SIUa](https://idearagon.aragon.es/SIUa/) devuelve una aplicación Angular;
  la extracción utiliza el archivo público que entrega los datos en HTML.
- [Plataforma Urbanística de Aragón](https://idearagon.aragon.es/PUA/): HTTP 200.
  Se inspeccionaron sus parámetros públicos de consulta y las cuatro categorías
  `TIPO=PlanGeneral`, `PlanDesarrollo`, `ProyDelimSueloUrbano`, `0`, todas con
  `CMUNIINE=22213`. Ninguna devolvió expedientes en esta consulta. Esto no prueba
  ausencia de planeamiento en tramitación. Las respuestas se conservaron.
- [Sede electrónica municipal](https://sarinena.sedipualba.es/): HTTP 200,
  identifica Ayuntamiento de Sariñena. Contiene trámites de solicitud de
  licencia/autorización urbanística, que se excluyen como formularios.
- [Tablón municipal vigente](https://sarinena.sedipualba.es/tablondeanuncios/):
  HTTP 200, 13 anuncios visibles en la consulta, principalmente empleo,
  ordenanzas y cobranza. No se convierten en proyectos ni licencias. El anuncio
  genérico de trámite de interés social no permite identificar por su título
  una actuación concreta, por lo que tampoco se extrae. Este tablón no se
  presenta como archivo histórico completo.
- [Transparencia municipal](https://www.xn--sariena-7za.es/transparencia):
  enlazada desde la sede; falló la resolución DNS en el runtime. También falló
  el acceso a la portada del mismo dominio. No se sustituyó su contenido con
  fragmentos de buscadores. Noticias de medios y anuncios de contratación no
  se utilizaron como inventario de proyectos.

## Semántica, identidad y documentos

La identidad es el `CODEXP` oficial COT/CPU de Huesca; su hash produce un ID
estable. Las filas con el mismo expediente se agrupan en un registro con toda
su `tramitacion`. Las rectificaciones de igual título pero distinto expediente
siguen siendo instrumentos distintos. PGOU y texto refundido tienen expedientes
oficiales distintos y no se fusionan por semejanza textual.

Cada evento conserva su fila de procedencia, título, resolución, enlace y fechas
de aprobación inicial, publicación inicial, aprobación provisional, acuerdo,
publicación del acuerdo, aprobación definitiva municipal, publicación municipal
y publicación de normas, según las columnas disponibles. No se intercambian
fechas de acuerdo y publicación. `fecha` queda nula. Las fechas vacías quedan
nulas y las fechas inválidas causan error.

La resolución y fecha de acuerdo superiores corresponden al evento más reciente
con fecha de acuerdo. `fecha_aprob` sólo procede de la columna explícita de
aprobación definitiva municipal o de un acuerdo que dice «Aprobar
definitivamente». Las aprobaciones parciales conservan el texto completo de la
resolución. Los informes favorables, suspensiones, renuncias y retiradas no se
convierten en aprobaciones. Puede existir una aprobación municipal posterior al
informe autonómico: ambas fechas y actos permanecen diferenciados. La fase
superior describe la última resolución autonómica disponible y no acredita
vigencia actual ni ejecución de obras.

Los enlaces originales a acuerdos y boletines se guardan con su campo y fila.
Los documentos `addDoc` se agrupan por expediente, se deduplican por identificador
del repositorio y conservan nombre, categoría y otros identificadores asociados.
Su `url` es la ficha oficial desde la que se descargan: **no es una URL directa
al PDF**. El sitio utiliza un formulario POST para la descarga documental; el
adaptador no inventa rutas de descarga ni descarga/interpreta los PDF. Cinco
expedientes no declaran documentos `addDoc`; siguen conservando su historial y
los enlaces que sí publica el inventario. Esto se refleja en validation.json.

No se extraen coordenadas ni geometrías de los planos. No se utiliza el centro
municipal, parcelas inferidas ni desplazamientos aleatorios. La consulta entrega
el inventario completo de una sola página, sin controles de paginación visibles.
El adaptador rechaza páginas que anuncien paginación nueva en vez de entregar
silenciosamente una parte. La actualización repite la instantánea completa y
sólo escribe el resultado después de validar inventario y todos los detalles.
Errores de red, identidad, campos o formato detienen la extracción.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_sarinena -v`: **8 pasadas**.
Cubren identidad municipal, agrupación y estabilidad, distintas fechas,
aprobación municipal frente a informe autonómico, suspensiones, navegación y
formularios sin registros, paginación inesperada, documentos, cambio de formato,
fallo de red sin reemplazar datos anteriores y configuración del manifest.

Extracción real mediante `load_manifest('sarinena')`,
`load_portal_adapter(manifest)` y `backfill_proyectos`: **19 registros**, 30 filas
de tramitación, 198 referencias de documentos del repositorio. El control
compartido de entidades informó 19 expedientes identificados, cero desconocidos.
Todas las coordenadas y geometrías son nulas. No se ejecutó ningún paso de
publicación ni acceso a servicios privados.

Evidencia local, no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json` y capturas originales `evidence/live/inventory.html`
y `evidence/live/detail-*.html`. La validación incluye las 20 URLs realmente
consultadas por el adaptador, conteos, runtime y limitaciones. Las capturas de
descubrimiento adicionales están en `evidence/`.
