# San Vicente de la Barquera — INE 39080, Cantabria

Verificado el 2026-11-09 con el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Adaptador de un inventario municipal real de planeamiento. Cobertura parcial;
no constituye un registro completo de proyectos, obras o licencias concedidas.

## Fuentes oficiales descubiertas

- https://aytosanvicentedelabarquera.es/ — portada municipal, HTTP 200.
  Ofrece Urbanismo y noticias de actuaciones. Las noticias y enlaces generales
  no se convierten en proyectos mediante coincidencias de palabras.
- https://aytosanvicentedelabarquera.es/urbanismo/ — fuente de extracción,
  HTTP 200, inventario público de documentos organizado en acordeones Elementor.
  Once secciones principales; los acordeones anidados son grupos documentales,
  no instrumentos independientes. No se observó paginación. El adaptador procesa
  todas las secciones y falla ante paginación o secciones principales desconocidas.
- https://transparencia.aytosanvicentedelabarquera.es/contratos-de-obras/ —
  inventario de contratación, HTTP 200. No se utiliza para inferir proyectos
  aprobados ni licencias; un anuncio de contratación no acredita esos hechos.

## Cobertura extraída

Ocho instrumentos, con documentos agrupados bajo su título municipal:

| Instrumento | Documentos principales |
| --- | ---: |
| Expediente 840/2025, estudio de detalle Paseo de la Barquera 22 y 61 | 4 |
| Expediente 1158/2025, estudio de detalle C/ Padre Ángel 14 | 7 |
| Expediente 512/2022, estudio de detalle Paseo de la Barquera 45 | 10 |
| Expediente 1566/2022, estudio de detalle Pº de la Barquera 61, 61B, 61C, 61D y 22 | 9 |
| Estudio de detalle Barrio Oyambre | 2 |
| PGOU San Vicente 2015 | 81 |
| Plan especial de protección y reforma interior del casco antiguo | 20 |
| Catálogo de edificaciones en suelo rústico (CESR) | 451 |

Los criterios de interpretación del PGOU se conservan como un documento
complementario de ese plan, con su propio título y URL, sin crear otro proyecto.
Las fichas individuales del CESR y planos del PGOU no se convierten en cientos
de proyectos. Cada enlace conserva el título y la página municipal de procedencia.
Se resuelven enlaces relativos y se deduplican URL dentro del instrumento.

Las otras dos secciones no generan registros: constitución de la Junta de
Compensación de Santa Marina (acto organizativo), y PORN del Parque Natural de
Oyambre (instrumento regional de ámbito supramunicipal). Los expedientes
840/2025 y 1566/2022 mantienen identidades diferentes: coincidir en direcciones
no demuestra que sean el mismo expediente o una modificación del otro.

## Semántica y límites

- El PGOU indica acuerdo CROTU 2015-05-21 y publicación BOC 2015-08-19.
  El plan especial indica acuerdo CROTU 1993-02-24, pero su publicación figura
  truncada como `19/07/1`; `fecha_publicacion` queda null. El CESR indica acuerdo
  plenario 2013-06-20 y publicación BOC 2013-07-17 en su título.
- `fecha_acuerdo` y `fecha_publicacion` se extraen por separado; `fecha` queda
  null. Las fechas de directorios de subida y años de expediente no son fechas
  de aprobación. La fecha de publicación de los criterios de interpretación no
  reemplaza la del PGOU. `fechas_fuente` conserva el texto de procedencia.
- Las fases de los estudios de detalle proceden de etiquetas explícitas de los
  documentos: inicial para 840/2025; definitiva para 1158/2025, 512/2022 y
  1566/2022. Oyambre no tiene fase verificada en las etiquetas. Los estudios
  conservan fechas null porque el HTML no las especifica; no se interpreta el
  texto de los PDF para completar esas fechas.
- No se afirma vigencia jurídica exhaustiva ni ejecución de obras. Se conserva
  lo publicado en este inventario. No se han recorrido todos los anuncios,
  boletines, noticias o contratos históricos del municipio.
- Se verificaron dos descargas representativas con HTTP 200 y cabecera PDF:
  https://aytosanvicentedelabarquera.es/file/PGOU/Memoria/1_Memoria.pdf y
  https://aytosanvicentedelabarquera.es/wp-content/uploads/2026/02/2026-668.pdf.
  No se han descargado ni verificado individualmente los 585 enlaces conservados.
  La extracción se basa en el índice HTML, no en contenido interpretado de PDF.
- Sin coordenadas ni geometrías verificadas; `lat`, `lon` y `geometry` null,
  `publication_ready: false`. No se sustituye por un centroide municipal.
  `schedule.enabled`, `geocode.jitter_missing` y `licencias.enabled` son false.
- Identidad estable por número de expediente o clave del instrumento, independiente
  de los documentos añadidos y fase. Update refresca el inventario completo;
  no mantiene un archivo histórico de retiradas. Las licencias producen una
  salida vacía con estado disabled, sin solicitudes ficticias.

## Validación reproducible

Desde la raíz del repositorio:

```bash
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_san_vicente_de_la_barquera -v
```

Resultado: seis tests correctos, con fixtures sintéticos independientes de red:
agrupación anidada y enlaces relativos, fechas distintas y truncadas, fases sin
fechas inventadas, identidades estables, exclusiones, rechazo de fuente vacía,
paginación y secciones desconocidas, carga del manifest y actualización.

Extracción real ejecutada con `load_manifest`, `load_portal_adapter` y
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`: status ok,
8 registros. La anotación compartida de categorías comunica 4 unknown de 8;
no se ha forzado una categoría para ocultar esta limitación.

Evidencia local no destinada al commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas HTML de Urbanismo, portada y contratos,
y dos PDF representativos. Validation registra runtime, hora UTC, cantidades,
URLs, limitaciones y SHA-256 de las capturas y la salida. Solo se añaden los
cuatro archivos fuente solicitados; sin cambios compartidos o dependencias.
