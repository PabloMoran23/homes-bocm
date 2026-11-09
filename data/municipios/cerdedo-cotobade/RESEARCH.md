# Cerdedo-Cotobade — INE 36902, Pontevedra

Verificación: 2026-11-09. Adaptador de inventario municipal de planeamiento,
con cobertura parcial y sin licencias. Se revisaron primero `municipio/manifest.py`,
`municipio/adapters/portal.py`, el registro de adaptadores y los ejemplos de Hernani
y Manlleu. No requiere cambios compartidos ni dependencias adicionales.

## Inventarios oficiales descubiertos

La fuente operativa es [Urbanismo del Concello](https://www.cerdedo-cotobade.gal/servizos/urbanismo/).
Tiene enlaces estáticos a seis páginas de planeamiento estatutario, además del
PMUS, la Axenda Urbana, formularios y noticias. El extractor descubre las seis
páginas desde el inventario en cada ejecución, sin fijar una noticia como semilla.
PMUS y Axenda Urbana se excluyen explícitamente por el alcance elegido. Noticias,
contratación y formularios no se convierten en proyectos ni licencias concedidas.

También se localizaron el [inventario de planeamiento del portal municipal de
transparencia](https://cerdedo-cotobade.portal-transparencia.org/t/planeamiento)
y [SIOTUGA de la Xunta](https://siotuga.xunta.gal/siotuga/urb), que identifica
36902 y los dos instrumentos generales históricos de Cerdedo y Cotobade.
Son vías complementarias de investigación, no fuentes recorridas por este
adaptador ni una garantía de cobertura completa de modificaciones posteriores.
El municipio fusionado conserva ámbitos distintos: PXOM de Cerdedo y NNSS de
Cotobade; ambos registros pertenecen al municipio actual 36902.

## Resultado comprobado

Extracción real mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos`: **8 registros, 129 enlaces documentales**.

| Página municipal bajo `/servizos/urbanismo/` | Instrumentos | Documentos |
| --- | ---: | ---: |
| `pxom-cerdedo/` | PXOM de Cerdedo | 75 |
| `plan-especial-dotacions/` | Plan especial de dotaciones | 9 |
| `normas-subsidiarias-cotobade/` | NNSS; modificación I; modificación III con corrección | 37 + 1 + 2 |
| `p-e-dotacions-vial-cerdedo-caroi/` | Plan especial vial Cerdedo-Caroi | 3 |
| `p-e-praza-san-xurxo/` | Plan especial de plaza en San Xurxo de Sacos | 1 |
| `plan-especial-de-infraestructuras-e-docacions-zona-verde-el-zv-30/` | Plan especial EL/ZV-30 | 1 |

Cada documento conserva título, URL publicada y página de procedencia. Los planos
no se convierten en proyectos adicionales. La corrección se incorpora a la
modificación III, no como nuevo instrumento. Los planos modificados/vigentes de
las NNSS se conservan en su inventario base con sus etiquetas: no se atribuyen a
una modificación concreta sin evidencia. Las tres versiones/archivos del vial
permanecen en el mismo instrumento, sin afirmar equivalencia de contenido.

Se excluyen enlaces Drive vacíos, incluido un enlace residual copiado en EL/ZV-30.
Se conservan enlaces externos etiquetados de Drive y adminmyweb tal como los
publica el Concello, incluidos HTTP y espacios en sus rutas; no se ha comprobado
el contenido de todos los archivos ni descargado el ZIP de 1,15 GB.
Se comprobó HTTP 200 y cabecera PDF en cinco documentos municipales de muestra:
normativa PXOM, NNSS I, documento de aprobación definitiva del plan de dotaciones,
modificación I y publicación BOP de modificación III. Esta comprobación puntual
no implica disponibilidad integral de los 129 enlaces.

## Fechas, estado y geometría

Las páginas ofrecen documentos de aprobación, pero no una fecha HTML explícita
con semántica inequívoca de publicación/acuerdo/aprobación. `fecha`,
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas. No se extraen
fechas del nombre de archivo, directorio de subida ni metadatos WordPress.
Tampoco se infiere aprobación de una etiqueta sin analizar su documento: la fase
queda sin asignar. La presencia en el inventario no acredita vigencia jurídica
actual ni ejecución de obras.

`geometry_status: unavailable`. Hay planos PDF/JPG, sin geometría vectorial
verificada y enlazable a cada instrumento. No se vectorizan mapas ni se inventan
coordenadas. `publication_ready: false`. Las licencias, la programación y el
jitter están deshabilitados en el manifest.

## Recorrido y validación reproducible

No hay paginación en las páginas estáticas revisadas. Ante marcadores de
paginación el parser falla explícitamente; no corta en un límite de páginas o
registros. También falla ante contenido ausente, inventario vacío, páginas sin
documentos, entradas nuevas sin clasificar o una corrección huérfana de la
modificación III. La escritura se realiza al terminar todas las páginas; un fallo
no sustituye la salida previa. `update_proyectos` refresca la instantánea completa.
No se recorre el histórico de noticias ni se promete un censo histórico municipal.

Pruebas ejecutadas con el runtime preinstalado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_cerdedo_cotobade -v
```

Cinco pruebas offline: descubrimiento y exclusiones; agrupación/deduplicación y
procedencia; fechas desconocidas; rechazo de paginación/cambios; conservación de
salida ante fallo; carga del manifest y licencias deshabilitadas.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json` y capturas HTML de inventario y detalles. Para repetir
la extracción se carga el adaptador por registro, se asigna opcionalmente
`adapter.config['evidence_dir'] = 'evidence'` y se llama a
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
