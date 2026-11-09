# Mota del Cuervo — Cuenca — INE 16133

Investigación y extracción en vivo: 9 de noviembre de 2026. Se han inspeccionado
`municipio/manifest.py`, el contrato `municipio/adapters/portal.py`, el cargador
`municipio/adapters/registry.py` y los ejemplos Chipiona, Manlleu y Hernani.

## Fuentes oficiales descubiertas y alcance

- [Mapa municipal](https://motadelcuervo.es/mapa-web): la versión indexada permite
  descubrir «Planeamiento Urbanístico», «Impresos Urbanismo» y «Planeamiento
  general y sus modificaciones». El contenido indexado sirve para descubrimiento,
  no para producir registros.
- [Inventario municipal de planeamiento general y modificaciones](https://motadelcuervo.es/tu-ayuntamiento/transparencia-municipal/urbanismo-y-medioambiente/84-2016-01-14-11-46-59/1412-planeamiento-general-y-sus-modificaciones):
  la petición real devuelve HTTP 500, con el mensaje
  `Failed to load 'g5_hydrogen' template: Please install Gantry 5 Framework!`.
  También fallaron portada, mapa, variante www, ruta index.php y vista de impresión.
  Se conserva la respuesta del inventario en evidencia; no se interpreta como vacío.
- [Sede electrónica, transparencia](https://motadelcuervo.sedelectronica.es/transparency/):
  responde HTTP 200. La sede ofrece trámites de solicitud de licencia; esto no
  acredita licencias concedidas. No se implementa un registro de concesiones.
- [Registro de PAUs de Cuenca de la JCCM](https://urbanismo.castillalamancha.es/registros/pau-cu):
  fuente operativa elegida. Tabla oficial actual con siete entradas provinciales
  en la consulta real, una de Mota del Cuervo. No había paginador en esa respuesta.
  El adaptador descubre y recorre todos los enlaces del paginador Drupal y
  `rel=next`, deduplica por URL de ficha y falla sin escribir un resultado parcial
  si una página no se puede interpretar o se alcanza el límite de seguridad.
- [Ficha del PAU 4/2006 «EL TESORO»](https://urbanismo.castillalamancha.es/registros/pau/pau-42006-el-tesoro-de-las-nnss-de-mota-del-cuervo-cuenca):
  fuente concreta del único registro extraído. Se verifican el tipo Drupal de PAU,
  título coincidente con el inventario y jerarquía territorial CUENCA / Mota del
  Cuervo. No se acepta una coincidencia de municipio dentro de un título ajeno.

El buscador también descubrió documentos municipales `images/docs/planeamiento.pdf`
y `images/2025/PROYECTO_VIA%20VERDE_MOTA%20vrecortada2.pdf`. No se han incorporado:
no se ha reconstruido un inventario documental municipal navegable ni se han
validado sus contenidos desde el runtime. Tampoco se convierten anuncios de
licitación, formularios o noticias generales en proyectos.

## Semántica y procedencia

La extracción es un registro regional de un instrumento urbanístico real, no una
licencia concedida ni una afirmación de obra ejecutada. El manifest usa
`proyectos.source: ayuntamiento` como canal de adaptador de portal admitido por
el esquema existente. La procedencia efectiva está declarada en las notas y en
cada fila: `source: jccm`, `organismo_fuente` y `origen` regional.

La tabla llama al 25/09/2020 «Fecha de constitución»; la ficha llama a esa fecha
«Fecha de aprobación». `fecha_aprob: 2020-09-25` se extrae únicamente del campo
etiquetado de la ficha, no del nombre técnico del campo ni de la columna del
listado. Se conservan por separado el texto y la etiqueta originales del listado.
La inscripción del 9 de noviembre de 2020 se conserva como texto original y no se
convierte en aprobación o publicación. `fecha`, `fecha_publicacion` y
`fecha_acuerdo` permanecen nulas. No se deduce vigencia, fase jurídica adicional,
fecha de ejecución o actualidad material del PAU.

Una fila por instrumento, identificada mediante hash estable de su URL. Las
capturas HTML conservan los campos originales. La ficha observada no contiene
adjuntos: `documentos: []` y la URL concreta siguen disponibles. Si aparecen
PDF/ZIP o enlaces de archivo en el artículo, se conservan agrupados y sin duplicar
el instrumento; no se buscan documentos en menús de navegación. No se afirma
haber descargado o analizado documentos que la ficha no expone. Se omite la
superficie mostrada, cuya presentación/unidad no se ha validado.

Cobertura **parcial**: solo PAUs presentes en el registro regional de Cuenca,
filtrados por municipio exacto. No cubre otros instrumentos, todas las obras,
licencias, histórico completo ni documentos inaccesibles del Ayuntamiento.
Sin geometría verificada: latitud, longitud y geometría nulas,
`geometry_status: unavailable`, `publication_ready: false`.
`schedule.enabled`, `geocode.jitter_missing` y `licencias.enabled` son false.

## Validación reproducible

Runtime preinstalado usado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Comando: `python -m unittest municipio.test_mota_del_cuervo -v`.
Siete tests correctos: identidad territorial exacta, rechazo de fuentes inválidas,
semántica de fechas, agrupación documental, ausencia de aprobación inferida,
paginación con deduplicación y fallo posterior sin sobrescribir la instantánea.
También se comprueban carga del manifest y licencias desactivadas.

Se cargó la clase mediante la especificación del manifest y se ejecutó
`backfill_proyectos(Path('evidence/proyectos.jsonl'))` con peticiones HTTP reales,
sin mocks. Resultado: **1 registro**, **1 página de inventario**, **1 ficha**.
`update_proyectos` actualiza la instantánea completa usando la misma extracción.
Los errores de estructura, identidad o red abortan la extracción antes de escribir.

Evidencia local, fuera de los cuatro archivos fuente y no destinada a commit:

- `evidence/proyectos.jsonl`: registro real.
- `evidence/validation.json`: contador `live_records`, URLs, fecha de comprobación,
  limitaciones, resultado de tests y HTTP 500 de la fuente municipal.
- `evidence/captures/*.html`: cuerpos originales de las respuestas del inventario
  regional y su ficha, nombrados por hash de URL.
- `evidence/municipal-planeamiento-response.html`: respuesta de error municipal.

No se han instalado dependencias, modificado fuentes compartidas ni usado bases
de datos, credenciales, publicación o despliegue.
