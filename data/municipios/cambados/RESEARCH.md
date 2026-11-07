# Cambados — INE 36006, Pontevedra, Galicia

Comprobado el 2026-11-07 con el runtime preinstalado. Cobertura parcial:
**19 instrumentos de planeamiento**, no licencias ni obras ejecutadas.

## Descubrimiento y fuentes oficiales

- https://cambados.es/ muestra «A web está en construción» y remite a la sede.
- https://cambados.sedelectronica.gal/info.0 contiene «PLANEAMENTO MUNICIPAL /
  NORMATIVA URBANÍSTICA», enlazado a
  https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36006 .
- La consulta normalizada usada por el adaptador es
  https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=36006 .
  SIOTUGA es el inventario de la Xunta de Galicia, no una colección de noticias.
  El formulario identifica expresamente 36006 = Cambados; cada detalle se valida
  además por municipio, ID y carpeta documental CAMBADOS.
- El JavaScript público `assets/inventario/controls.min.js?2.5.0` documenta las
  peticiones POST a `assets/inventario/query_document.php` (`id=36006`,
  `idclase=14/13/18`) y `assets/inventario/getIOTPU.php`
  (`iddoc=<ID descubierto>`, `idp=0`, `lang=gl_ES`). Se utiliza el valor anti-CSRF
  del formulario público anónimo, sin autenticación ni credenciales.

## Cobertura y semántica

Clase 14: 7 instrumentos de planeamiento general, incluidas las Normas
Subsidiarias y modificaciones puntuales. Clase 13: 12 instrumentos de desarrollo
(planes parciales, especiales, modificaciones y estudios de detalle).
Clase 18: respuesta `null`, sin delimitaciones de núcleo rural.
Las **672 entradas documentales** permanecen agrupadas bajo sus 19 IDs oficiales;
un documento que aparece en varios grupos conserva sus contextos originales.
No se convierten las hojas cartográficas, catálogos o correcciones en proyectos.

Los cinco estudios de detalle 25741, 25430, 26021, 24650 y 26770 tienen ficha e
identidad oficial pero `elementos=null`: se conservan con `documentos=[]` y
`document_coverage=no_components_available_in_source`. No se inventan documentos.
Una muestra de memoria PDF enlazada respondió HTTP 200 con firma `%PDF-`.
No se han descargado ni validado individualmente los 672 componentes.

Los campos de fecha se conservan por significado: `fechaaddef` → `fecha_aprob`,
`fechadog` → `fecha_publicacion_dog`, `fechabop` → `fecha_publicacion_bop`,
`fechanormativabop` → `fecha_publicacion_normativa_bop`.
`fechatextodef` se conserva como `fecha_texto_refundido_fuente`.
`fecha` y `fecha_publicacion` genérica quedan nulas; no se toma una fecha de
boletín por fecha de acuerdo. Las incidencias jurídicas se conservan en ambas
formas (inventario y detalle). No se infiere vigencia jurídica ni fase actual
por el mero hecho de figurar en este catálogo. No son nueva actividad de 2026.

Se excluye explícitamente la clase histórica 16 (3 entradas observadas, una con
incidencia de denegación). También se excluyen instrumentos supramunicipales de
ordenación territorial y anuncios de contratación. La sede tiene formularios de
solicitud de licencia, que no acreditan concesiones; licencias deshabilitadas.
No se cubre un histórico completo de proyectos municipales ni obras públicas.

## Paginación, identidad y geometría

La interfaz recibe arrays JSON completos y luego usa DataTables en cliente;
no envía parámetros de página ni tamaño en estas consultas. Se procesa cada
array entero sin límite de registros y todos sus componentes. Una respuesta
que cambie a un sobre paginado se rechaza, al igual que IDs conflictivos,
fechas discrepantes o un inventario global vacío. Los métodos de actualización
refrescan la instantánea completa y escriben el resultado de forma atómica.

El identificador estable es `cambados-siotuga-<id oficial>`. La procedencia
incluye URL, método y parámetros públicos de cada consulta, sin tokens.
No se atribuye a estos IDs un número de expediente municipal inexistente.

`geometry_status: unavailable`. SIOTUGA anuncia visor y WMS; este adaptador
retiene los planos enlazados pero no ha verificado geometrías vectoriales
asociadas a cada instrumento. No extrae polígonos de imágenes ni inventa
coordenadas; `lat`, `lon` y `geometry` quedan nulos, `publication_ready=false`.

## Validación y límites de integración

`PYTHONDONTWRITEBYTECODE=1 /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_cambados -v`

Cuatro pruebas comprueban agrupación documental y fechas distintas, arrays
completos (125 elementos), duplicados, respuestas paginadas inesperadas,
municipios incorrectos, cambios de esquema, falta explícita de documentos,
rutas documentales y configuración del manifest/licencias.

La extracción real se ejecutó mediante `load_manifest('cambados')` y
`load_portal_adapter`, con capturas en `evidence/`. Produce 19 filas.
El anotador compartido de entidades clasifica las 19 como `pendiente` y emite
`adapter_incident/unknown_entity_spike`: sus reglas no reconocen la identidad
del catálogo SIOTUGA sin número de expediente municipal. Se conserva esa salida
sin inventar referencias para obtener elegibilidad y sin modificar código
compartido. Estos registros requieren revisión antes de cualquier ingestión.

Evidencias locales no destinadas a commit: `proyectos.jsonl`, `validation.json`,
resultado del anotador, capturas HTML/JSON/JS comprimidas y comprobación del PDF.
El disco estuvo temporalmente lleno; volvió a disponer de espacio antes de la
extracción definitiva. Sólo se añaden los cuatro archivos fuente solicitados.
Programación y jitter deshabilitados; no se realizó publicación alguna.
