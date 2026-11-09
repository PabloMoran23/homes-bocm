# Navalvillar de Pela — INE 06091, Badajoz, Extremadura

Investigación y extracción real: 2026-11-09. Adaptador único, sin ejecución
programada, sin geocodificación artificial y sin extracción de licencias.

## Descubrimiento y fuentes oficiales

La página municipal de [Urbanismo](https://navalvillar.com/areas/urbanismo/)
describe servicios y procedimientos, pero no presenta un inventario de proyectos.
La consulta web permitió examinarla; las peticiones Python tanto a navalvillar.com
como a www.navalvillar.com devolvieron HTTP 403. La página de
[instancias](https://navalvillar.com/ayuntamiento/instancias-y-solicitudes/) ofrece
formularios, que no constituyen licencias concedidas. No se interpretan noticias,
formularios, contratación de personal ni anuncios de licitación como proyectos.

Se utiliza el [buscador avanzado oficial del DOE](https://doe.juntaex.es/busquedas/bus_avanzada.php),
descubierto desde su portada. El formulario publica los filtros de fechas,
organismo y título. El adaptador envía dos POST a
https://doe.juntaex.es/busquedas/disposiciones.php desde 2024-01-01 hasta la fecha
actual: uno por `orgabus=NAVALVILLAR DE PELA`, otro por
`textobus=Navalvillar de Pela`, `yuo=0`, `buscardesc=nodesc`, sin filtro de rango
o materia. La segunda consulta incorpora las publicaciones autonómicas que no
aparecen bajo el organismo municipal. No se fijan noticias individuales como
semillas. `end_date` permite repetir una fecha de corte y `capture_dir` guardar HTML.

Se verificaron **18 y 56 disposiciones**, respectivamente. El parser exige que el
número de filas coincida exactamente con el total anunciado; si aparece paginación
o cambia el formato, falla antes de escribir. No acepta silenciosamente una primera
página. Se deduplican las URLs de detalle por identificador XML, año y DOE.

## Registros genuinos y agrupación

El alcance deliberado son dos instrumentos identificados, con seis publicaciones:

* **UE3, zona 3**: consulta de viabilidad publicada 2024-01-03; aprobación inicial
  acordada 2025-02-13 y publicada 2025-02-28; aprobación definitiva acordada
  **2025-04-10** y publicada **2025-07-10**. El programa contiene proyecto de
  urbanización, actualización del proyecto de reparcelación y asunción de
  ordenación detallada; forman un solo registro con tres documentos, no tres obras.
  [Publicación definitiva](https://doe.juntaex.es/otrosFormatos/html.php?xml=2025081129&anio=2025&doe=1320o).
  Su cabecera dice «Anuncio de 2 de junio», pero el cierre dice «2 de julio»;
  `fecha_documento` reproduce la cabecera, sin resolver esa discrepancia ni
  convertirla en fecha del acuerdo.
* **Modificación puntual 1/2019 (n.º 20), Cooperativa San Isidro Labrador**:
  informe ambiental estratégico IA24/0077 de 2024-05-09 publicado 2024-05-17;
  aprobación inicial acordada **2024-11-14**, publicada 2025-02-17; aprobación
  definitiva acordada **2025-10-21**, publicada **2025-12-18**.
  [Acuerdo definitivo](https://doe.juntaex.es/otrosFormatos/html.php?xml=2025AC0105&anio=2025&doe=2430o).
  Se agrupan las denominaciones 20-1/2019 y 1/2019 (n.º 20). El informe ambiental
  se vincula por expediente IA24/0077 y manzana delimitada por Cantarranas,
  Luis Chamizo, Velázquez y Adolfo Suárez; el acuerdo definitivo describe esa misma
  manzana y cita expresamente el informe de 09/05/2024. No se confunde el
  informe ambiental con aprobación del instrumento ni con licencia municipal.

Cada documento conserva título, organismo, fecha de publicación, fecha de cabecera,
fase, URL HTML y enlaces PDF auténtico/XML. Las fechas de acuerdo se extraen sólo
del pasaje correspondiente o de una cabecera explícita de ACUERDO, nunca de la
fecha genérica del anuncio. El registro agregado toma la última publicación del
instrumento, y retiene las publicaciones anteriores. Las seis referencias PDF se
comprueban y capturan durante la validación local. El HTML DOE advierte que es
informativo y que el PDF constituye la versión auténtica.

## Cobertura y límites

Inventario parcial de **dos instrumentos**, no inventario íntegro del municipio.
La selección sólo soporta UE3 y modificación 20-1/2019; otros proyectos privados,
expedientes ambientales, instalaciones eléctricas, otros planes e histórico anterior
a 2024 quedan fuera. La consulta es por metadatos de organismo/título, no por todo
el contenido de cada boletín. No se declara que las obras estén ejecutadas, ni
que no existan cambios posteriores publicados en otras fuentes. `fase` es la
última documentada en esta cobertura. Los métodos de actualización vuelven a leer
la misma ventana completa, sin simular un cursor incremental.

El DOE es el repositorio de publicación: `source=ayuntamiento` identifica el
canal de proyectos municipales del contrato compartido; `origen`, `inventory_url`
y el organismo de cada documento conservan la procedencia real, incluida CUOTEX.
No se descargan ni interpretan los proyectos técnicos completos de la sede.
No se han obtenido geometrías verificadas asociadas a estos instrumentos;
`geometry_status=unavailable`, `publication_ready=false`, sin coordenadas ni
centroides. No se verifica un registro de licencias concedidas; licencias está
deshabilitado. Una pérdida futura de resultados o un cambio de estructura requiere
revisión, no se sustituye por datos de ejemplo.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_navalvillar_de_pela -v
```

Cuatro pruebas offline: integridad del inventario/paginación, agrupación y
separación de fechas, vinculación ambiental, exclusiones y carga del manifest.
La extracción live se ejecutó mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`manifest.portal.config['capture_dir']='evidence/captures'`. Se conservan localmente
`evidence/proyectos.jsonl`, `evidence/validation.json`, HTML y PDFs bajo `evidence/`.
La validación incluye consultas POST completas, URLs, conteos y limitaciones.
No se modifican dependencias, registro compartido ni fuentes de otros municipios.
