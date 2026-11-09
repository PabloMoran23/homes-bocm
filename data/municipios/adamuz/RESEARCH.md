# Adamuz — Córdoba — INE 14001

Investigación y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales descubiertas

- Ayuntamiento: https://adamuz.es/ (también https://www.adamuz.es/ redirige allí).
  Tanto la portada como `/urbanismo/` devolvieron HTTP 403.
- Portal municipal: https://transparencia.adamuz.es/ y la ruta candidata
  `/urbanismo-obras-publicas-y-medio-ambiente/` devolvieron HTTP 403. La ruta
  candidata no se considera un inventario verificado. Los resultados de búsqueda
  contienen actas, pero no se usan como registros extraídos ni como prueba de
  acceso actual a un inventario completo.
- La Junta identifica SITUA como consulta de documentación de instrumentos:
  https://www.juntadeandalucia.es/organismos/viviendajuventudyordenaciondelterritorio/areas/urbanismo/situa.html
- **Inventario utilizado, consultado en vivo**:
  https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf
  Municipio `14001`, nombre `Adamuz`, consulta `aprobado` (Planes urbanísticos y
  territoriales aprobados). La tabla resultante muestra planeamiento general.
  El formulario público JSF y su endpoint DataTables
  https://ws132.juntadeandalucia.es/situadifusion/pages/figuras.jsf
  son accesibles con sesión anónima. El listado devuelve provincia CÓRDOBA y
  municipio ADAMUZ; se comprueban ambos campos para cada fila.
- Descubrimiento complementario, fuera de la cobertura del adaptador:
  https://www.juntadeandalucia.es/boja/2022/168/42 (HTTP 200, captura local)
  publica la subsanación de una modificación del PGOU para equipamiento en
  Algallarín. Esto confirma que las dos entradas de la consulta general no son
  un inventario exhaustivo de modificaciones. No se crea un registro precargado
  a partir de esa URL ni se atribuye el anuncio a una obra ejecutada.

## Extracción y cobertura

Resultado real: **2 instrumentos, 70 documentos únicos dentro de sus fichas**:

| Código SITUA | Figura y objeto del inventario | Fecha de aprobación según SITUA | Documentos |
|---|---|---|---|
| 3866 | NNSS - Normas Subsidiarias Municipales; objeto: 1995 | 27/01/1995 | 55 |
| 86900 | PAP - Procedimiento de Adaptación Parcial; Adaptación Parcial a la LOUA de las Normas Subsidiarias | 09/05/2019 | 15 |

Las fechas se extraen de `Fecha de Aprobación`, coincidente entre listado y ficha;
no son fechas de publicación. La fecha de actualización de SITUA no se usa como
fecha de acuerdo. Se conserva el estado de la ficha como `estado_fuente`, sin
convertirlo en una fase ni afirmar la vigencia jurídica verificada de todo el
planeamiento. `fecha_publicacion` queda nula. No se inventan coordenadas,
geometrías, licencias concedidas ni fechas de ejecución. `publication_ready` es
falso y `geometry_status` indica ausencia de geometría.

El código de instrumento define el registro; memorias, normas, planos,
certificaciones y boletines se agrupan en `documentos`. La ficha incluye un
array JSON `mapa` con referencias repetidas por cada nodo de su árbol documental;
se deduplican por URL y se retienen las claves de agrupación originales. Se
contrasta el número de documentos únicos con todas las filas de la tabla de
exportación oculta de la ficha. No se limita la lectura al nodo seleccionado ni
a los documentos visibles en la primera página de la interfaz.

La paginación del inventario es **de servidor**. El adaptador solicita
`iDisplayStart` e `iDisplayLength=10` y continúa hasta consumir exactamente
`iTotalDisplayRecords`. En la ejecución real el total fue 2 y se consumieron las
dos filas. Un total cambiante, páginas vacías prematuras, identificadores
repetidos o metadatos inconsistentes provocan error sin sustituir el resultado
anterior. No hay límite de páginas que trunque silenciosamente el listado.

Cobertura parcial: únicamente planeamiento general aprobado de Adamuz que la
consulta SITUA devuelve actualmente. No comprende todos los instrumentos de
desarrollo, modificaciones, obras públicas, archivos municipales o expedientes
en tramitación. El registro incluye fuente `junta_andalucia`, URL de consulta y
parámetros reproducibles. `proyectos.source: ayuntamiento` en el manifest
selecciona el pipeline del adaptador municipal según el esquema existente;
no atribuye a la web municipal los documentos autonómicos.

## Acceso documental y comprobaciones

Los enlaces `descargaDocumentos.jsf?doc=...` se retienen tal como los publica
SITUA, sin identificadores de sesión. **Requieren abrir previamente la ficha en
una sesión anónima del portal**. Un GET aislado devolvió página de error con
HTTP 200; no se confundió con una descarga válida. Tras consultar el municipio y
abrir Documentos del Plan del instrumento en la misma sesión, se comprobó una
descarga por instrumento: documentos `81514` y `198868`, ambos HTTP 200,
`application/pdf` y firma `%PDF`. Se guardaron sus primeros 4096 bytes; no se
verificó el contenido íntegro de los setenta PDF. La URL principal del registro
es la consulta oficial y `source_request` conserva la navegación necesaria.

Pruebas: `python -m unittest municipio.test_adamuz -v` usando el runtime indicado:
7 pruebas correctas. Cubren agrupación y deduplicación documental, fechas
explícitas, rechazo de formularios/noticias, aislamiento de municipio e
instrumento, documentos incompletos, consumo de varias páginas y fallos de
paginación sin sobrescribir resultados, manifest y licencias desactivadas.

Se ejecutó realmente `load_portal_adapter(load_manifest('adamuz')).backfill_proyectos`
(con directorio local de capturas en config), incluyendo la política compartida
de entidades. Esa política anotó ambos registros como categoría desconocida:
la evidencia no afirma una clasificación temática validada.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, respuestas HTML/JSON en `evidence/live/`, capturas de
investigación y prefijos PDF. La validación consigna `live_records`, URLs,
limitaciones, fecha de ejecución, recuento documental y comprobaciones de PDF.
No se han modificado fuentes compartidas ni dependencias, y no se ha usado
publicación, base de datos o geocodificación. Actualizaciones rehacen esta misma
instantánea; no prometen un histórico completo. `schedule.enabled=false`,
`geocode.jitter_missing=false` y `licencias.enabled=false`.
