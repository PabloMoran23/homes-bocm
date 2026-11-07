# Valle de Trápaga-Trapagaran — INE 48080, Bizkaia

Consulta en vivo: 2026-11-07. Adaptador limitado al inventario municipal de
**proyectos de urbanización**, no a todos los expedientes del municipio.

## Descubrimiento y selección

Navegación oficial comprobada por HTTP GET:

- [Urbanismo](https://www.trapagaran.net/es-ES/Servicios/Urbanismo/Paginas/default.aspx)
- [Planeamiento y gestión](https://www.trapagaran.net/es-ES/Servicios/Urbanismo/Paginas/Planeamientoygestion.aspx)
- [Inventario de proyectos de urbanización](https://www.trapagaran.net/es-ES/Servicios/Urbanismo/Paginas/Proyectosdeurbanizacion.aspx)

El inventario contiene Ibarzaharra 06, AIS-IB-06, e Ibarzaharra 04,
URB-036-2021. El segundo conserva la errata UBR en las URL del ayuntamiento;
no se corrigen ni reconstruyen esos enlaces. No se emplean noticias individuales
como semillas. Se siguen las páginas descubiertas desde el inventario.

También se comprobaron los inventarios de planeamiento urbanístico, gestión,
expedientes en tramitación, otros planes y la página del PGOU con sus índices de
documentación escrita/gráfica. Quedan fuera del alcance de este adaptador. El
apartado de información pública menciona Ibarzaharra 07 (URB-349-2014), pero no
ofrece allí una ficha documental enlazada que el extractor de este inventario
pueda recorrer. Por tanto los dos registros no representan el total municipal.

El [catálogo oficial de Open Data Bizkaia](https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-trapagaran)
se revisó como alternativa. El recurso de datos globales 2023–2026 es una serie
estadística trimestral de superficies/viviendas, no un inventario de proyectos:
se excluye de la extracción. Su modificación de octubre de 2026 no es una fecha
de aprobación urbanística. Se conserva una captura local para poder comprobarlo.

## Agrupación, fechas y procedencia

Un registro por ficha de proyecto, con ID derivado de su URL municipal estable.
Los capítulos, fases 0/1/2, planos, estudios, autorizaciones y anuncios vinculados
se agrupan como documentos del mismo árbol. Los anexos relacionados de PAU,
reparcelación o convenio de Ibarzaharra 04 se conservan con sus títulos originales;
no generan proyectos adicionales ni licencias.

Cada documento incluye URL, título y lista de páginas/secciones de procedencia.
`paginas_fuente` conserva todas las páginas recorridas, incluidas las paginadas;
`textos_fuente` conserva las narrativas con su URL. Se deduplican documentos por
URL, reteniendo las distintas apariciones. El extractor recorre todos los enlaces
HTML y `?page=N` descubiertos; no fija un número de páginas a extraer. Los límites
de seguridad abortan sin reemplazar el JSONL anterior, nunca entregan un corte.
Un cambio a paginación mediante postback provoca error explícito.

Ibarzaharra 06: la narrativa identifica publicación en BOB 145, **2020-07-30**,
de la aprobación inicial del texto refundido. Solo esa fecha se extrae como
`fecha_publicacion`. El PDF BOB enlazado fue descargado y comprobado: confirma
que afecta a Sestao y Valle de Trápaga-Trapagaran, y menciona decretos de ambos
ayuntamientos de 2020-07-17. La tramitación corresponde a Sestao según el anuncio.
El adaptador no interpreta fechas de PDF: `fecha_acuerdo` y `fecha_aprob` quedan
nulas. No se confunde aprobación inicial con definitiva o ejecución.

Ibarzaharra 04: hay ramas de aprobación inicial y definitiva y un anuncio cuyo
título se refiere expresamente a aprobación definitiva del proyecto. Se conserva
el documento y su sección sin convertir etiquetas o nombres de archivo en fechas.
El anuncio descargado no proporciona texto extraíble con pdftotext; no se aplica
OCR ni se infieren fechas. La fase normalizada queda nula al faltar narrativa en
la ficha principal. Los documentos permiten al revisor examinar su tramitación.

## Geometría y límites

`geometry_status: unavailable`. La página oficial del PGOU enlaza
http://www.udalgeo.com/Trapaga/web/map.asp?MPID=200101&Idioma=es.
Se comprobó la entrada HTTPS de Udalgeo, pero no se ha verificado una geometría
vectorial vinculada a los dos expedientes. Los planos PDF/DWF no se convierten en
geometría; latitud, longitud y geometría son nulas, `publication_ready=false`.

La extracción registra documentos enlazados; no descarga ni interpreta todos los
PDF, algunos muy grandes. No acredita vigencia jurídica actual, avance de obra,
terminación, adjudicación o concesión de licencia. Licencias y programación están
deshabilitadas y no hay jitter de coordenadas. Las actualizaciones son snapshots
completos del mismo inventario, sin estado incremental ficticio.

## Reproducción y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Pruebas: `python -m unittest municipio.test_valle_de_trapaga_trapagaran -v`.
Seis pruebas offline verifican procedencia, agrupación, recorrido de paginación
con ciclos, fechas, error de estructura y preservación del snapshot anterior.
Las fixtures de prueba son sintéticas, no registros entregados.

Extracción directa: instanciar
`ValleDeTrapagaTrapagaranAyuntamientoAdapter('valle-de-trapaga-trapagaran',
{'capture_dir': 'evidence/captures'})` y llamar
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`.

Evidencias locales excluidas de entrega de fuentes: `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas HTML de cada GET y dos PDF oficiales de
comprobación. La validación registra conteo real, URLs y limitaciones. No se usa
orquestador, publicación, base de datos ni servicios con credenciales.

Resultado en vivo: **2 proyectos**, **99 páginas HTML**; 471 documentos en Ibarzaharra 06; 56 documentos en Ibarzaharra 04.
Cierre del grafo comprobado: todos los enlaces HTML descubiertos constan entre
las URLs visitadas. La rama Fase 1 y 2 llega a `?page=52`.
