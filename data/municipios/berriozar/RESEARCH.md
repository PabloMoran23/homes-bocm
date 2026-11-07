# Berriozar — Navarra — INE 31903

Verificado el 7 de noviembre de 2026 mediante solicitudes públicas reales.
Adaptador único: `municipio.adapters.berriozar:BerriozarAyuntamientoAdapter`.

## Descubrimiento y fuentes oficiales

El inventario municipal actual de ordenación territorial enlaza directamente SIUN:
https://www.berriozar.es/transparencia/informacion-sobre-ordenacion-territorial-urbanismo-medio-ambiente-y-vivienda/

Destino oficial vigente:
https://administracionelectronica.navarra.es/SIUN_Consulta/Index.html#/inicio

El inventario municipal anterior sigue accesible:
https://www.berriozar.es/general/transparencia/urbanismo-obras-publicas-y-medioambiente/planes-de-ordenacion-urbana-y-convenios-urbanisticos/
Su enlace `siun.navarra.es/Resultados.aspx?muni=903` presenta un error de certificado
al usar HTTPS. No se desactiva la comprobación TLS: se utiliza el destino actual,
verificado desde la página municipal actual. Los enlaces antiguos del BON se
contrastaron con las páginas oficiales actuales:

- https://bon.navarra.es/es/anuncio/-/texto/2017/169/22 — publicación normativa de las NNSS, que incluye textos de los planes parciales Zortziko y Berriaintz.
- https://bon.navarra.es/es/anuncio/-/texto/2017/224/8 — recopilación de modificaciones 1991–2017, que no constituye un proyecto adicional independiente.

También se revisó la página municipal del Plan de Movilidad Urbana Sostenible:
https://www.berriozar.es/ayuntamiento/proyectos-municipales/plan-de-movilidad-urbana-sostenible/
Describe un plan en elaboración y enlaza medidas de participación. No se incorpora
al alcance PG ni se presenta como aprobación. Tampoco se extraen formularios,
licitaciones, convenios genéricos o noticias como licencias concedidas.

## Inventario utilizado y paginación

La aplicación pública expone sus peticiones en
`Angular/services/siunConsultaPublicaDataFactory.es5.min.js` y sus filtros en
`Angular/services/utilsService.es5.min.js`, bajo la misma base SIUN.
No requiere autenticación. La consulta `api/Municipios` identifica expresamente
`903 = BERRIOZAR`. Cada detalle se verifica además con provincia **31**, municipio
**903** y nombre **BERRIOZAR**. Se mantienen las relaciones de los siete instrumentos
supramunicipales, sin atribuir exclusivamente a Berriozar todo su ámbito.

Petición pública de búsqueda (POST de consulta, sin mutación de datos):
`api/Instrumentos/PG/default/false/{offset}/25`, con cuerpo:

```json
{"municipios":[903],"entidadesPoblacion":[],"tiposInstrumento":[],"aprobadoPosterior":false}
```

`aprobadoPosterior=false` incluye el histórico anterior al planeamiento general
actual. Se recorren todas las páginas indicadas por `pagedInfo`: offsets
**0, 25, 50, 75, 100 y 125**, total **149**. Se comprueban el total constante, el
número de páginas, el tamaño esperado de cada página y la ausencia de IDs repetidos.
Una respuesta incompleta, un cambio de total, un detalle inválido o un error HTTP
aborta antes de reemplazar la salida. No existe un límite que recorte registros.

Cada ID descubierto se consulta en `api/Instrumentos/{id}`. En la salida, `url`
apunta a la ficha pública `Index.html#/instrumento/{id}`, `source_url` al JSON
exacto e `inventario_municipal_url` a su procedencia municipal. No hay lista fija
de proyectos ni registros derivados de resultados de un buscador.

## Semántica, documentos y cobertura

Una fila por ID oficial de instrumento. Los 447 enlaces de `instrumentosDocumentos`
se agrupan en `documentos` con ID, título, escala, tipo original y procedencia;
los trámites y enlaces BON permanecen dentro del instrumento. Los documentos no
se convierten en proyectos adicionales. Se conserva `idPadre` cuando existe.
Los tipos y descripciones proceden de la API, sin reclasificar un anuncio como obra.

La plantilla pública `Angular/views/instrumentos/view.html` etiqueta `fecha` de
cada trámite como **Fecha BON** y `fechaResolucion` como **Fecha de resolución**.
Se conserva esta distinción en cada trámite. `fecha_publicacion` es la primera
fecha BON del instrumento con número de boletín, que puede corresponder a su fase
inicial. `fecha_aprob` solamente usa una fecha de resolución explícita de un
trámite con fase Definitiva y resolución Aprobación; nunca usa `fechaDefinitiva`
como sustituto. Se conservan las fechas de cabecera bajo `fechas_siun` con sus
nombres originales. `fecha` genérica y `fecha_acuerdo` quedan nulas.

Ejemplo real: estudio de detalle SIUN **111329**, parcela 367 del polígono 18,
expediente original `0009-OT05-2023-000173`: resolución definitiva **2023-09-27**,
publicación de esa resolución **2023-11-10**; publicación inicial **2023-07-20**.
Las NNSS SIUN **2652** conservan 14 documentos; el BON municipal enlazado publica
su normativa en 2017, sin convertir esa fecha en una nueva aprobación del plan.

Cobertura parcial: exclusivamente la pestaña **PG** del registro SIUN, incluyendo
histórico, tramitación y sus indicadores de estado originales. No incluye la
pestaña OT, el conjunto de obras municipales, PMUS ni un registro de licencias.
Los indicadores SIUN no constituyen una comprobación jurídica independiente de
vigencia. En la captura las publicaciones con número BON abarcan 1996-05-01 a
2025-08-19; no se afirma cobertura exhaustiva hasta 2026. Los 47 instrumentos sin
adjuntos conservan su ficha oficial, sin inventar documentos. Se retienen los
142 enlaces a documentos escritos y 305 a visores; no se ha descargado ni validado
el contenido de todos los adjuntos.

126 fichas tienen `numExpediente=null`. Se mantiene el ID oficial de instrumento
sin fabricar un número de expediente. El clasificador compartido las deja como
`pendiente` y devuelve `adapter_incident / unknown_entity_spike`; las otras 23
quedan como `expediente`. Es una limitación explícita para revisión y publicación,
no ausencia de los registros oficiales. No se modifican las reglas compartidas.

## Geometría

`geometry_status: unavailable`, `geometry`, `lat` y `lon` nulos;
`publication_ready: false`. SIUN proporciona enlaces gráficos, por ejemplo
clasificación del suelo de las NNSS 2652, en `gissiun.tracasa.es`. Una comprobación
real devuelve un envoltorio HTML que requiere dimensiones de visor. Se conservan
las URL originales completas de la API; no se ha extraído una capa vectorial ni
un polígono verificable por instrumento. Los planos o visores no se convierten
en coordenadas aproximadas. `geocode.jitter_missing=false`.

## Validación y reproducción

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_berriozar -v
```

Cinco pruebas pasan: agrupación documental y fechas, identidad territorial,
metadatos de paginación, recorrido completo/rechazo de duplicados sin reemplazo
parcial y configuración/licencias deshabilitadas. No dependen de capturas locales.

La extracción real se ejecutó mediante `load_manifest('berriozar')` y
`load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
añadiendo solamente en memoria `manifest.portal.config['capture_dir'] =
'evidence/sources'`. Resultado: **149 registros / 6 páginas / 447 enlaces**,
139 registros con fecha de publicación y 20 con fecha explícita de resolución
definitiva. La anotación compartida está incluida en la evidencia.

Evidencias locales no destinadas a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json` (conteos, fuentes, limitaciones), `evidence/sources/`
(inventario municipal, catálogo de municipios, seis páginas y 149 detalles),
y capturas adicionales de descubrimiento. Actualizar vuelve a leer la instantánea
completa; no escribe un estado incremental ficticio. Licencias y programación
están deshabilitadas. No se ha publicado ni usado base de datos o despliegues.
