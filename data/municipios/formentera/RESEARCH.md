# Formentera — INE 07024, Illes Balears

Verificado mediante HTTP directo el 7 de noviembre de 2026. El Consell Insular
publica documentación de ordenación urbanística del municipio de Formentera.
No se han utilizado fuentes comerciales, formularios de solicitud, contratación
ni noticias como sustitutos de proyectos o licencias concedidas.

## Descubrimiento y fuente utilizada

El área oficial de Urbanismo y Ordenación del Territorio contiene un menú curado
de instrumentos de planeamiento y sus documentos:

https://www.consellinsulardeformentera.cat/index.php?option=com_content&view=category&id=110&Itemid=525&lang=ca&layout=default

Se lee ese menú completo, no las noticias del cuerpo de la página. Se siguen
sus artículos, las subentradas del menú y los enlaces a artículos dentro del
contenido de cada instrumento. Los identificadores Joomla se canonizan sin
Itemid ni alias para evitar duplicar un artículo por su posición en el menú.
No hay paginación en el menú curado observado. Si aparece paginación dentro
del menú o de un artículo se falla explícitamente. No hay límite de filas o
páginas que pueda cortar silenciosamente esta colección.

Otros inventarios oficiales descubiertos pero **fuera de cobertura**:

- Categoría 342, información pública de normativa en vigor y en tramitación:
  https://www.consellinsulardeformentera.cat/index.php?option=com_content&view=category&id=342&Itemid=427&lang=ca
  Es un archivo paginado, con publicaciones más recientes que el menú curado,
  incluidas actuaciones de 2026. No se afirma haber recorrido este archivo.
- Categoría 345, expedientes y otros anuncios urbanísticos:
  https://www.consellinsulardeformentera.cat/index.php?option=com_content&view=category&id=345&Itemid=415&lang=ca
  No se convierte una información pública o un expediente en licencia concedida.

## Extracción real y agrupación

Resultado: **7 instrumentos, 13 artículos fuente, 91 URLs documentales** (únicas
dentro de cada instrumento), conservando títulos, enlaces y páginas de procedencia.

| Instrumento | Artículos Joomla | Documentos |
| --- | --- | ---: |
| Modificación PTI 6, equipamientos e infraestructura des ca Marí | 9958, 9957, 8715 | 15 |
| Modificación PTI 5, adaptación a la Ley agraria | 7673, 7674 | 3 |
| Modificación PTI 4 y texto/documentación gráfica refundida 2020 | 7083, 7082, 6249 | 22 |
| Modificación PTI 3, ordenación turística | 6304 | 1 |
| Modificación PTI-NS 2, redelimitación de conjuntos históricos | 4707 | 13 |
| Modificación NNSS 1 y texto/planimetría refundidos 2013 | 2490, 2491 | 18 |
| Revisión NNSS 2010 | 897 | 19 |

Ejemplos de páginas de documentación:

- https://www.consellinsulardeformentera.cat/index.php?option=com_content&view=article&id=9957&lang=ca
- https://www.consellinsulardeformentera.cat/index.php?option=com_content&view=article&id=7082&lang=ca
- https://www.consellinsulardeformentera.cat/index.php?option=com_content&view=article&id=2490&lang=ca
- https://www.consellinsulardeformentera.cat/index.php?option=com_content&view=article&id=897&lang=ca

Las fases inicial y definitiva y sus memorias, anexos, planos, certificados y
publicaciones BOIB se agrupan por modificación. El texto refundido de 2013 se
asocia a la modificación 1 porque su propio texto la identifica; el parser
comprueba esa relación. Los documentos no se emiten como proyectos adicionales.
Los enlaces repetidos entre artículos mantienen todas sus páginas de procedencia.
La revisión 2010 se mantiene como instrumento histórico separado de sus enmiendas.
La presencia en este inventario no acredita por sí sola la vigencia jurídica de
cada determinación histórica. La fase es la anunciada por la fuente, no una
certificación jurídica del estado actual.

`fecha_publicacion` sólo corresponde a `.rt-date-posted`, la fecha del artículo
municipal. Se conserva también por página fuente; la del artículo principal puede
ser nula aunque otra página del instrumento esté fechada. Por ejemplo, la página
9957 se publicó el 17-05-2023 y enlaza un certificado del Ple de 31-03-2023: esas
fechas no son intercambiables. No se analizan las fechas jurídicas dentro de los
PDF o sus rótulos; `fecha_acuerdo`, `fecha_aprob` y la fecha genérica quedan nulas.
No se infieren fechas a partir de nombres de archivos, años o identificadores.

## Límites y geometría

Cobertura parcial del menú documental; no todo el archivo histórico, convenios,
obras públicas ni planeamiento de la isla. Las actualizaciones vuelven a leer la
colección completa, sin cursor de fechas. Se aborta antes de sustituir el JSONL
si falta la estructura esperada, un instrumento carece de documentos o aparece
una entrada/enlace de artículo sin clasificar.

Se retienen enlaces de documentos municipales, BOIB y BOE tal como se publican.
No se descarga ni verifica exhaustivamente su disponibilidad. Se comprobó y
capturó un PDF real: memoria justificativa de la modificación 6 (1.938.565 bytes,
HTTP 200, cabecera `%PDF-`). Los controles Joomla de imprimir, correo y exportar
el artículo a PDF se excluyen como documentos originales.

`geometry_status: unavailable`. Hay planos PDF y enlace a Catastro en el menú,
pero no se ha verificado geometría vectorial asociada a estos instrumentos. No
se extraen coordenadas ni se vectorizan planos. `lat`, `lon` y `geometry` nulos;
`publication_ready: false`. No se ha verificado inventario de licencias concedidas;
los métodos de licencias producen vacío deshabilitado.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_formentera -v` — **4 pasan**. Cubren
agrupación de fases y alias, canonicalización, fechas de publicación, procedencia,
exclusión de controles Joomla, rechazo de contenido/paginación/entradas inesperadas,
recorrido de artículos hijos, deduplicación documental y conservación de la salida
anterior ante error. No requieren red ni capturas locales.

Extracción real: se cargó el manifiesto con `load_manifest('formentera')`, se
instanció `FormenteraAyuntamientoAdapter` con `capture_dir='evidence/captures'`
y se ejecutó únicamente `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.

Evidencias locales, no destinadas a commit:

- `evidence/proyectos.jsonl`: 7 registros reales.
- `evidence/validation.json`: recuentos, comprobaciones, URLs, límites y mapa de capturas.
- `evidence/captures/*.html`: menú y 13 artículos del recorrido real.
- `evidence/mod6-memoria-justificativa.pdf`: comprobación documental puntual.

Manifiesto con `schedule.enabled=false`, `geocode.jitter_missing=false` y
`licencias.enabled=false`. Sin cambios compartidos, dependencias, bases de datos,
publicación o despliegue. Requiere revisión independiente (`accepted=false`).
