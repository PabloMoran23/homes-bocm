# Fuentes de Ebro — Zaragoza — INE 50115

Comprobación en vivo: 2026-11-09. Adaptador único del tablón público municipal.

## Descubrimiento e inventarios oficiales

- https://www.fuentesdeebro.es/ enlaza la sede electrónica y el tablón municipal.
- https://www.fuentesdeebro.es/tablon-de-anuncios/ es un archivo de entradas
  WordPress (nueve páginas anunciadas), principalmente convocatorias de plenos,
  empleo y ayudas. No se extrae ese archivo ni se afirma haber recorrido sus páginas.
- https://fuentesdeebro.sedelectronica.es/board es el inventario seleccionado:
  tabla HTML `AdvertisementBoardListPanel`, filtro «Todos», seis anuncios actuales
  y sin navegación de páginas en la respuesta revisada. Se procesa la tabla completa.
  Si aparece navegación activa, se aborta con error, sin escribir una página parcial.
- https://idearagon.aragon.es/SIUa/archivo/buscador?CMUNIINE=50115 es el archivo
  regional de planeamiento localizado durante la búsqueda. La petición HTTP directa
  devuelve la aplicación JavaScript, sin filas. No se extrae ni se presenta como
  cobertura histórica o como fuente de los dos registros obtenidos.

Las capturas de estas cuatro fuentes están bajo `evidence/`. El tablón y los
previews/PDF se capturaron otra vez mediante el propio adaptador en la prueba real.
No se usan agregadores, formularios, convocatorias de contratación ni noticias
para acreditar proyectos o concesiones.

## Resultado y procedencia documental

Dos expedientes reales, agrupados por el identificador municipal, con un documento
cada uno en esta instantánea:

1. **1610/2026**: proyecto de obras de ejecución de red de pluviales en calle Doctor
   Fleming, fase I. Publicación en el tablón **2026-10-28**.
   https://fuentesdeebro.sedelectronica.es/preview-document/5bfb4b44-59b2-4625-a119-489072643300
   El PDF municipal identifica expresamente la aprobación inicial del proyecto,
   el objeto y al Ayuntamiento como promotor. Aunque el procedimiento de la tabla
   dice «Contrataciones», el documento es un anuncio de aprobación del proyecto,
   no una licitación. Su título «Anuncio en el Boletín Oficial de la Provincia» no
   implica que el PDF sea una página del BOP: es el anuncio municipal firmado.
   La firma del 20/10/2026 no se transforma en fecha del acuerdo.
2. **1504/2026**: estudio de detalle en calle Mariano José de Larra, anuncio de
   aprobación inicial. Publicación en el tablón **2026-10-09**.
   https://fuentesdeebro.sedelectronica.es/preview-document/011df895-3344-49ff-a3a0-144f84973994
   El nombre del documento refiere al Heraldo de Aragón del 8 de octubre, fecha
   distinta de la publicación en sede. El instrumento y el trámite se extraen de
   la descripción municipal de la fila. El PDF es accesible, pero no ofrece texto
   en `pdftotext`; no se hace OCR ni se deduce una fecha de acuerdo de esa imagen.

Se guardan enlaces estables a los previews, títulos originales, descripciones,
procedimiento y fecha de publicación de cada documento. Los enlaces temporales de
los PDF se descubren en cada preview y se descargan para comprobar su firma `%PDF-`.
Se conservan copias locales; no se publica un enlace temporal como identificador.
Los documentos de un expediente no generan proyectos independientes. La fecha de
publicación del registro agrupado es la primera de sus documentos presentes.
`fecha_acuerdo` y `fecha_aprob` permanecen nulas. No se inventan fases finales.

## Cobertura y límites

Instantánea vigente, sin reconstrucción histórica ni anuncios retirados. La
actualización vuelve a leer el inventario, sin convertirlo en un archivo histórico.
Se seleccionan anuncios explícitos de aprobación inicial/provisional/definitiva de
instrumentos de planeamiento, reparcelación, urbanización o proyectos de obras.
Los restantes cuatro anuncios actuales (empleo, minería e información de jurado)
quedan fuera. No existe registro comprobado de licencias concedidas: métodos de
licencias vacíos y deshabilitados. Un futuro tablón vacío o sin instrumentos
compatibles exige revisión y genera error, no una salida vacía silenciosa.

`geometry_status: unavailable`: no geometría vinculada a estos expedientes en el
inventario revisado; latitud, longitud y geometría nulas. No se extraen coordenadas
de mapas ni PDFs. `publication_ready: false`. Agenda deshabilitada y
`geocode.jitter_missing: false`.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_fuentes_de_ebro -v`: cuatro pruebas pasan.
  Cubren agrupación/deduplicación, fechas, exclusión de licitaciones/formularios,
  detección de paginación, cambios de esquema/procedencia y carga del manifest.
- Extracción real con `load_manifest('fuentes-de-ebro')`,
  `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
  Para capturas se estableció `manifest.portal.config['capture_dir'] = 'evidence'`
  solo en memoria. Resultado: **2 registros**, dos previews y dos PDF verificados;
  política de entidades aplicada por el registro compartido, sin desconocidos.
- Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`, HTML y
  documentos originales. La conversión local de PDFs se conserva como comprobación
  auxiliar y no forma parte del parser ni aporta fechas de aprobación.

No hay cambios compartidos, dependencias nuevas, publicación ni acceso a bases de datos.
