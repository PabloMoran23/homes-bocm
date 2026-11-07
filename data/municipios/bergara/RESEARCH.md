# Bergara — INE 20074, Gipuzkoa

Verificación y extracción en vivo: 2026-11-07. Se revisaron previamente el contrato
`municipio/adapters/portal.py`, el cargador de manifests y los ejemplos Hernani y
Manlleu. No se modifican fuentes compartidas, dependencias ni registro de adaptadores.

## Inventario oficial y alcance

Fuente de descubrimiento: [Urbanismo municipal](https://www.bergara.eus/es/node/517),
HTTP 200. Es un índice Drupal Book, no una búsqueda de noticias. El adaptador lee
los enlaces hijos del índice dentro de `article #book-navigation-517 > ul.menu`.
Selecciona planes especiales (incluida la modificación del plan del casco histórico
en euskera), estudios de detalle, proyectos de urbanización y reparcelación.
Sigue los capítulos subordinados de cada instrumento y conserva los enlaces a
documentos municipales y al Boletín Oficial de Gipuzkoa, con títulos y páginas de
procedencia. No se convierten memoria, presupuesto, planos o anuncios en proyectos
separados. Las URLs de detalle se descubren en vivo, sin una lista fija de expedientes.

Resultado: **10 instrumentos documentados, 169 enlaces documentales**, procedentes
de 11 entradas del índice y un capítulo subordinado de planos. Se descargaron 13
páginas HTML contando el índice. Los documentos se conservan como enlaces; no se
afirma haber descargado ni validado individualmente todos los PDFs.

| Instrumento | Página municipal | Enlaces |
| --- | --- | ---: |
| Estudio de detalle parcelas 2 y 3 A-44 | https://www.bergara.eus/es/node/16786 | 3 |
| Estudio de detalle Amillaga 15 y 19 | https://www.bergara.eus/es/node/16892 | 2 |
| Proyecto de urbanización modificado A44-2 | https://www.bergara.eus/es/node/19063 | 16 |
| Primera modificación plan especial del casco histórico | https://www.bergara.eus/es/node/17731 | 127 |
| Plan especial A-44 | https://www.bergara.eus/es/node/18774 | 5 |
| Plan especial modificado/adaptado A-18 | https://www.bergara.eus/es/node/20827 y /es/node/19972 | 6 |
| Estudio de detalle parcela H, Larramendi | https://www.bergara.eus/es/node/15538 | 4 |
| Plan especial A-17 | https://www.bergara.eus/es/node/19293 | 2 |
| Reparcelación A-44 | https://www.bergara.eus/es/node/20223 | 2 |
| Tercera modificación reparcelación UE40a-1 | https://www.bergara.eus/es/node/20990 | 2 |

La agrupación A-18 está respaldada por el [anuncio BOG del 07-10-2024](https://egoitza.gipuzkoa.eus/gao-bog/castell/bog/2024/10/07/c2407071.htm),
que identifica el plan modificado/adaptado y sus trámites anteriores. Las dos páginas
municipales se retienen en `fuentes` y `source_urls`, con procedencia de cada documento.
El capítulo [Plano orokorrak](https://www.bergara.eus/es/node/17889) aporta 30 enlaces
al mismo instrumento del casco histórico, no 30 proyectos.

La página de Larramendi H adjunta además un archivo denominado estudio de las
parcelas D/E/F/G. Se retiene su enlace con `relacion` explícita de otras parcelas;
no se atribuye ese estudio al instrumento H ni se genera otro proyecto sin verificarlo.
Los cinco enlaces del plan A-44 incluyen dos URLs diferentes de aprobación definitiva
con nombres parecidos; se retienen ambas, sin suponer que sus bytes son idénticos.

## Límites, fechas y semántica

Cobertura parcial del índice actual: se excluyen noticias, formularios, convocatorias,
convenios, cambios de sistema de actuación, desistimientos, mapa de ruido y recursos
genéricos. Tampoco se recorre aquí el árbol del Plan General, sus modificaciones ni
el plan de accesibilidad. No es un histórico exhaustivo de obras ni un registro de
licencias concedidas. El índice mezcla documentos antiguos y recientes, sin garantía
de vigencia jurídica actual. No se infiere la fase a partir del título del adjunto.

`fecha_publicacion` y la fecha genérica quedan nulas: el HTML no ofrece una fecha
municipal inequívoca de publicación. Las fechas de URLs BOG no se reutilizan como
fechas municipales ni de acuerdo. Solo se extrae `fecha_acuerdo` cuando el texto
expresa inequívocamente un decreto: 24-03-2022 en parcelas 2/3 A-44 y 23-09-2021
en Larramendi H. En este último caso la firma es del día 24 y la publicación del
BOG del día 30: ninguna sustituye al acuerdo del día 23. Amillaga contiene el error
tipográfico `2I de abril`; no se corrige ni inventa la fecha. No se analizan fechas
en PDFs. El texto municipal se conserva en `fuentes[].descripcion` para revisión.

Los identificadores derivan de nodos municipales y de la agrupación documental
A-18, no son números administrativos de expediente. `source_entity_type: documento`
describe esta identidad documental comprobada; no declara eventos de actividad.
La anotación compartida clasifica los diez registros como documentos, sin incidencia
de entidades desconocidas. No se inventa una referencia de expediente para activar
contadores de actividad.

El índice revisado no tiene paginación de resultados. `.page-next` pertenece a la
navegación entre capítulos; seguirla como paginación mezclaría noticias y otros
servicios. Se recorren los enlaces hijos del árbol y se detectan ciclos. Si aparece
un paginador de resultados (`.pager`, `.pagination`, `rel=next`), se falla de forma
explícita antes de escribir una extracción parcial. Un capítulo ausente o un
instrumento sin documentos también aborta sin reemplazar el snapshot anterior.
`update_proyectos` repite el snapshot completo; no supone eliminación jurídica de
instrumentos que dejen de figurar en la web.

## Geometría

`geometry_status: unavailable`. Las páginas examinadas contienen enlaces documentales,
sin geometría vectorial vinculada a estos instrumentos. Se revisó también
[Mapas y planos](https://www.bergara.eus/es/node/663), cuyo contenido presenta un
mapa toponímico/interactivo; no se verificó una capa por identificador de instrumento.
No se vectorizan planos PDF ni se inventan coordenadas o CRS. `lat`, `lon` y
`geometry` son nulos; `publication_ready` es falso.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_bergara -v
```

Seis pruebas: selección y exclusiones del inventario; fechas de decreto frente a
firma/publicación; documentos deduplicados con procedencia; capítulos hijos frente
a hermanos; rechazo de paginación/cambios de estructura; agrupación A-18 y snapshot
atómico ante fallos; carga del manifest. Se ejecutó el adaptador real mediante
`load_portal_adapter(load_manifest('bergara'))`, exclusivamente `backfill_proyectos`.
Evidencias locales: `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/captures/*.html`, captura del BOG A-18 y de mapas. La validación incluye
recuento, URLs consultadas, limitaciones y resultado de política de entidades.
No se publican ni se incluyen las evidencias en los cuatro archivos fuente.

Manifest: INE `20074`, Bergara, Gipuzkoa; `schedule.enabled=false`,
`licencias.enabled=false`, `geocode.jitter_missing=false`.
