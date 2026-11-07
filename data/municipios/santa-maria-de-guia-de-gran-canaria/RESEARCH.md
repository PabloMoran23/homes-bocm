# Santa María de Guía de Gran Canaria — INE 35023

Provincia: Las Palmas. Comunidad autónoma: Canarias. Verificación: 2026-11-07.

## Fuentes oficiales y elección

- Inventario municipal: https://santamariadeguia.es/area-de-desarrollo-urbanismo/
  HTTP 200. La tabla distingue Planeamiento en Trámite, Planeamiento Aprobado y
  Normas y Ordenanzas. El extractor delimita exclusivamente Planeamiento Aprobado;
  no utiliza menús ni pies de página, que repiten enlaces y documentos.
- Portal documental PGO enlazado por ese inventario como «Plan General en Vigor»:
  https://www.plangeneralguiagc.es/PGO2017/inicio.html — HTTP 200.
  Se normaliza el enlace municipal HTTP a HTTPS y las barras inversas/espacios
  de los enlaces del portal. Su atribución municipal se establece por el enlace
  del ayuntamiento, además de la identificación explícita en la portada.
- Inventario autonómico descubierto y consultado, no mezclado con los registros:
  https://opendata.sitcan.es/api/3/action/package_show?id=planeamiento-urbanistico-de-santa-maria-de-guia-de-gran-canaria
  HTTP 200, ocho recursos; metadatos modificados el 2025-10-10. Publicado por el
  Gobierno de Canarias, sistematización GRAFCAN. Captura local `evidence/sitcan.txt`.
  Es otro producto y puede representar versiones históricas diferentes.
- Archivo autonómico descubierto:
  https://www3.gobiernodecanarias.org/aplicaciones/archivoplaneamientopt/pages/consulta/islaMunicipio.jsp?municipio=23&provincia=35
  No se utiliza como fuente de fechas o de cobertura exhaustiva del adaptador.
- La sede https://santamariadeguia.sedelectronica.es/info.0 publica trámites de
  urbanismo. Los formularios y comunicaciones no acreditan licencias concedidas.
- Existe un anuncio oficial posterior del trámite inicial de una modificación:
  https://www.gobiernodecanarias.org/boc/2026/076/pda/1277.html
  La modificación del SUSO R6 Barranco de Las Garzas queda fuera de esta tabla.
  Su existencia impide considerar el inventario elegido un registro completo de
  todo el planeamiento actual. No se incorpora una noticia o anuncio aislado como
  si fuese un inventario municipal completo.

## Registros y documentos

La ejecución real produjo **3 instrumentos** y **10 enlaces PDF**, todos comprobados
con HTTP 200 y firma `%PDF-` mediante lectura inicial de la respuesta:

- Plan General de Ordenación: 3 documentos enlazados directamente en portada
  (PPAA y EEFF, certificado de corrección de error material e índice del documento).
- PERI La Atalaya: ordenanzas generales y planos, agrupados en un único instrumento.
- PEPRI Guía: catálogo de viviendas, ordenanzas y planos 6.1, 6.2 y 6.3,
  agrupados en un único instrumento.

Se propaga el nombre de instrumento de la tercera columna sobre las filas
sucesivas vacías; cada documento conserva título, URL y página de procedencia.
Los documentos no generan registros independientes. No se deriva una fecha de las
rutas de subida `2020/08` ni del nombre del certificado `3460.21`.

La narrativa de portada del PGO identifica acuerdo/aprobación definitiva del
**2017-05-08**, publicación íntegra de normativa en BOP del **2017-06-30** y entrada
en vigor del **2017-07-21**. Se extraen por contexto en campos separados. `fecha`
genérica queda nula. La fecha del BOP no se presenta como publicación de la página
web. PERI y PEPRI no tienen fechas de acuerdo/publicación verificadas: campos nulos.
Su fase expresa la clasificación municipal «aprobado», sin certificar su vigencia
jurídica actual ni inferir un acuerdo administrativo concreto.

## Límites, paginación y geometría

Cobertura parcial: tabla estática de planeamiento aprobado publicada actualmente,
sin archivo histórico, obras, licencias, formularios, contratación, noticias,
planeamiento pendiente o normas generales. Las categorías sin enlaces no acreditan
cero instrumentos en el municipio. No se recorre cada sección anidada del portal
PGO: se conservan la portada y el índice PDF para acceder al documento completo;
los tres enlaces recogidos no se presentan como todos sus tomos o planos.

No hay paginación en las dos páginas utilizadas. El extractor rechaza enlaces
«siguiente», `rel=next` o contenedores de paginación, en vez de truncarlos.
Falla ante ausencia/cambio de tabla, planes desconocidos, documentos huérfanos o
pérdida de los instrumentos revisados. Las actualizaciones son instantáneas
completas; `state_path` no implica un histórico incremental ni una cola de borrados.

geometry_status: unavailable

El ayuntamiento enlaza https://visor.grafcan.es/visorweb/ como callejero. SITCAN
ofrece datos sistematizados descargables, pero no se ha verificado una unión de
geometrías con estos tres instrumentos/versiones. Los planos PDF no se vectorizan.
No se inventan coordenadas, CRS ni centroides. `publication_ready` es falso.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_santa_maria_de_guia_de_gran_canaria -v`
— **4 pruebas pasan**. Cubren límites de tabla, continuación de documentos,
deduplicación, fechas por contexto, procedencia, fallo ante cambios/paginación,
resolución del manifiesto y salida de licencias vacía. Fixtures sintéticos para
comportamiento; los registros de evidencia provienen de peticiones reales.

Extracción mediante `load_manifest` y `load_portal_adapter`, ejecutando
`backfill_proyectos(Path('evidence/proyectos.jsonl'))` con `capture_dir` local.
Resultados locales: `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/document_checks.json` y HTML en `evidence/captures/`. La validación
registra recuento real, URLs, limitaciones y hora UTC. La comprobación PDF es de
accesibilidad/firma, no una auditoría del contenido de todos los planos.

Solo cuatro fuentes nuevas. Sin cambios compartidos ni dependencias; licencias,
programación y jitter deshabilitados. Sin publicación, base de datos ni despliegue.
