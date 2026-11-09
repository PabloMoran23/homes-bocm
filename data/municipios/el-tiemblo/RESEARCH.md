# El Tiemblo — INE 05241, Ávila

Verificación en vivo: 2026-11-09. Un único adaptador municipal, sin publicación.

## Descubrimiento y procedencia

La página oficial municipal [Urbanismo y Obras](https://www.eltiemblo.es/urbanismo)
separa formularios de solicitud y normativa. Su enlace «Ver normativa» conduce al
[inventario PLAU de la Junta de Castilla y León para provincia 05, municipio 241](https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&pager.sortname=fPublicacion&pager.sortindex=-3&provincia=05&municipio=241).
El archivo identifica expresamente «TIEMBLO (EL), Código INE: 05241». Son fuentes
oficiales diferentes: descubrimiento municipal y documentos alojados por la Junta;
no se atribuye al Ayuntamiento la publicación del archivo autonómico.

El extractor vuelve a comprobar el enlace municipal y el INE en cada ejecución.
No usa una noticia individual ni una lista de proyectos escrita a mano. La búsqueda
web sirvió para descubrir el portal; los registros proceden del HTML oficial vivo.
Los formularios no acreditan licencias concedidas y no se extraen como registros.

## Inventario, cobertura y agrupación

El listado actual contiene **21 entradas**, paginadas **1–15 y 16–21**. Se recorren
los controles «Siguiente» de JCyL, incluidos sus parámetros JavaScript codificados,
conservando municipio, provincia y ámbito. Se comprueba continuidad, total constante,
número de filas y ausencia de ciclos. Una página ausente, un control desconocido o
una tabla modificada provocan error antes de reemplazar el fichero de salida.
No hay corte por fecha, ni límite silencioso de páginas o registros.

La cobertura elegida y declarada es el **libro PU, planeamiento urbanístico**:
**15 instrumentos reales**, con **41 enlaces a ficheros**, agrupados en su instrumento
por `cDocId`. Incluye las Normas Subsidiarias (277024), modificaciones y planes
parciales de Playas de Ávila, Las Laderas y El Pinar de la Atalaya. Las modificaciones
son instrumentos distintos del plan original; memorias, normas, planos, catálogos y
guías son documentos hijos, nunca proyectos adicionales.

Se excluyen explícitamente las **cinco entradas GU** (gestión urbanística) y la
**entrada OT** (PORN de Valle de Iruelas). No se solicita «Mostrar históricos».
Esto no equivale a todo el histórico urbanístico, todas las obras públicas ni todos
los expedientes municipales. El archivo puede incorporar documentación con retraso.
La anomalía de fechas de la entrada GU 301392 (publicación 04/03/2026, acuerdo
23/03/2026) se observó durante la investigación; esa entrada queda fuera del ámbito
PU y no se corrige ni se utiliza para fechar otros instrumentos.

Los listados de ficheros revisados no tienen paginación. El parser rechaza nuevos
controles de paginación en ellos para exigir una revisión antes de aceptar datos
parciales. Se conservan enlaces oficiales estables `openFichero.do?cFicheroId=…`,
eliminando únicamente `jsessionid`, además del listado de origen y del boletín cuando
este está enlazado en el inventario. No se afirma haber descargado los 41 PDFs.

Una entrada, **MODIFICACIÓN PUNTUAL( PTO.24/01)**, carece tanto de fichero como de
`cDocId` y fecha publicada: se conserva como instrumento inventariado con enlace al
inventario, documentación vacía y un ID técnico derivado de la fila. Este ID no se
presenta como número de expediente oficial y puede cambiar si cambia la fila.
**Seis entradas no tienen fecha de publicación**; queda `null`.

## Fechas, documentos y geometría

`fecha_publicacion` y `fecha_acuerdo` reproducen sus columnas de origen. No se
rellenan `fecha_aprob`, fecha de concesión, fase o estado de ejecución a partir del
título, tipo o ubicación en el archivo. `fecha` genérica permanece `null`.

Como comprobación documental se descargó el fichero oficial `AV277nrm.pdf`, listado
bajo las Normas Subsidiarias 277024, mediante `openFichero.do?cFicheroId=25565`.
HTTP 200, `application/pdf`, 14.920.096 bytes; redirección oficial a
`http://www.jcyl.es/plaupdf/05/05241/277024/AV277nrm.pdf`.
Es un PDF escaneado: su primera página muestra «Normas Subsidiarias de El Tiemblo»,
«Diciembre 1994» y un sello de aprobación provisional. Esa portada **no** acredita
una aprobación definitiva en 1994. El registro mantiene separadas las fechas del
archivo (publicación 27/03/1996, acuerdo 25/01/1996) y la procedencia del documento;
no se inventa una fecha de aprobación a partir del sello.

El inventario enlaza al [visor SIUR](https://idecyl.jcyl.es/siur/index.html?id=05241).
No se ha verificado una capa vectorial vinculada a cada instrumento. Los planos
escaneados no se convierten en coordenadas ni polígonos. `geometry_status` es
`unavailable`, geometría y coordenadas son nulas, `publication_ready` es `false`.

## Pruebas y evidencia reproducible

Runtime utilizado, sin instalar dependencias:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```bash
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_el_tiemblo -v
```

**5 pruebas pasan**: fechas separadas y vacías, identidad y normalización de enlaces,
rechazo de truncamiento/cambio de ámbito, documentos agrupados y paginación de
ficheros desconocida, recorrido completo de dos páginas con exclusiones, refresco
idempotente y preservación de salida ante error, licencias deshabilitadas y manifest.
Las fixtures son sintéticas y sólo se usan en pruebas, nunca como evidencia viva.

Se ejecutó `load_portal_adapter(load_manifest('el-tiemblo')).backfill_proyectos(...)`
con `capture_dir` local. La extracción real devuelve 15 registros, 21 filas revisadas,
2 páginas y 41 documentos enlazados. Evidencia local, fuera de los cuatro fuentes:

- `evidence/proyectos.jsonl`: registros reales con anotación del guard compartido.
- `evidence/validation.json`: recuentos, URLs realmente consultadas, límites y pruebas.
- `evidence/captures/`: HTML municipal, ambas páginas y los 14 listados de ficheros.
  Los nombres son SHA-256 abreviados de la URL registrada en `source_urls`.
- `evidence/normas-subsidiarias-277024.pdf` y su primera página PNG: muestra documental.

**Limitación del guard semántico compartido:** clasifica los 15 instrumentos como
`pendiente`, con `adapter_incident / unknown_entity_spike`, al no reconocer estas
identidades de catálogo como expedientes administrativos. No se inventan referencias
`expte` ni se modifica el guard para eludirlo. Son instrumentos extraídos de un
inventario oficial con sus documentos, pero requieren revisión semántica antes de
cualquier ingestión/publicación. La evidencia declara este resultado; `ready` describe
la disponibilidad del scraper para revisión, no una autorización de publicación.

`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.
Sin modificaciones compartidas, dependencias nuevas, bases de datos ni despliegues.
