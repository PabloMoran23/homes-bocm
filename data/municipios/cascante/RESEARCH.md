# Cascante — Navarra — INE 31068

Verificación en vivo: 9 de noviembre de 2026. Adaptador:
`municipio.adapters.cascante:CascanteAyuntamientoAdapter`.

## Descubrimiento y fuentes oficiales

- Área municipal de Urbanismo: https://cascante.es/tu-ayuntamiento/urbanismo/
  HTTP 200. Identifica Cascante, Navarra, y enlaza la sede electrónica y SIUN
  (Sistema de Información Urbanística de Navarra). Su relación de funciones y
  enlaces a formularios no acredita licencias concedidas.
- Inventario municipal de anuncios:
  https://cascante.es/tu-ayuntamiento/anuncios-municipales/ — HTTP 200.
  Página extensa con anuncios históricos, cobros, convocatorias, participación
  urbanística y contratación. No es un registro de obras ni de licencias.
  Se conserva captura de descubrimiento; no se convierte cada PDF en proyecto.
- Inventario utilizado: https://cascante.sedelectronica.es/board — HTTP 200.
  Tablón público actual, accesible sin identificación. Tabla HTML estructurada
  `AdvertisementBoardListPanel`, con documento, expediente, procedimiento,
  categoría, descripción y **Fecha de Publicación**. Se revisaron las nueve filas
  visibles y no hay controles de paginación. El extractor recorre todas las filas;
  si aparecen controles de paginación, incluidos controles AJAX de Wicket, falla
  explícitamente y exige revisión antes de aceptar una salida parcial.

## Registros realmente extraídos

Dos instrumentos, cada uno con un documento PDF verificado desde su vista pública:

| Expediente municipal | Instrumento anunciado | Publicación en tablón |
| --- | --- | --- |
| 1033/2026 | Aprobación inicial de modificación de la EUR-15 del Plan General de Cascante | 2026-10-15 |
| 952/2026 | Aprobación inicial del proyecto de reparcelación del sector 1.1 del AR-1 | 2026-10-08 |

Procedencia documental:

- https://cascante.sedelectronica.es/preview-document/5a7863c8-664b-4f96-bcaa-b9099bf7f3d6
  — documento titulado «Anuncio - Boletín Oficial de Navarra» en el tablón.
- https://cascante.sedelectronica.es/preview-document/b01a6744-2b4e-4c99-94b9-6bd568a94faf
  — documento titulado «anuncio bon» en el tablón.

El adaptador abre cada vista, descubre su iframe PDF y descarga el PDF usando la
misma sesión anónima y Referer. Los enlaces PDF son dependientes de la sesión;
se conserva el enlace estable de vista documental y SHA-256 de los bytes, en vez
de guardar como enlace permanente el token temporal del iframe. Las capturas
locales incluyen HTML y PDF. Se comprueba HTTP y cabecera de archivo `%PDF-`.
No se extrae texto de los PDF ni se afirman sus fechas de acuerdo/publicación BON.
La prueba exploratoria con `pdftotext` produjo texto con codificación de fuentes
defectuosa; no se usó para rellenar fechas.

La descripción del tablón identifica el instrumento y su aprobación inicial; el
título genérico del documento no genera una entidad distinta. Se agrupa por
expediente municipal, deduplicando documentos y conservando descripción, enlace,
procedimiento y fecha de cada anuncio. `fecha_publicacion` del grupo es la menor
fecha de publicación observada en sus documentos; no es el inicio del expediente.
Si hay anuncios de varias fases, la fase del grupo queda nula y cada documento
conserva su fase. La fecha de creación de una vista documental tampoco se
interpreta como acuerdo. `fecha`, `fecha_acuerdo` y `fecha_aprob` quedan nulas.

## Cobertura y exclusiones

Cobertura **parcial del tablón vigente**, no histórico completo ni censo de obras.
Se aceptan anuncios con aprobación explícita de instrumentos identificables
(plan general/municipal/parcial/especial, estudio de detalle o reparcelación),
solo en procedimientos de Planeamiento General o Actuaciones Urbanísticas.
No se incorpora el proyecto de ponencia de valoración catastral, recaudación,
empleo social, jurados, formularios ni anuncios de licitación. Tampoco se importa
la noticia del Plan Urbanístico de 2023 como si fuese un nuevo instrumento actual.

No se ha establecido un registro público de **licencias concedidas**:
`licencias.enabled=false`, y ambos métodos de licencias producen salida vacía
con estado `disabled`. El refresco de proyectos vuelve a leer la instantánea
completa; la desaparición del tablón no prueba revocación. Una fuente vacía,
estructura cambiada, documento perdido o paginación nueva produce error antes
de reemplazar la salida anterior.

## Geometría

`geometry_status: unavailable`. La página de Urbanismo enlaza SIUN mediante
http://www.navarra.es/home_es/Temas/Territorio/Urbanismo/SIUN/.
No se ha verificado una capa vectorial enlazable por expediente a estos dos
instrumentos. No se asignan centroides municipales, coordenadas inventadas ni
geometrías extraídas de planos. `lat`, `lon` y `geometry` quedan nulos y
`publication_ready=false`. `geocode.jitter_missing=false`.

## Validación y reproducción

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_cascante -v` con ese runtime,
**7 pruebas correctas**. Cubren identidad y fechas, agrupación/deduplicación,
exclusiones, separación de expedientes y fases, paginación/estructura/documentos
incorrectos, verificación PDF, conservación de la salida ante fallo y manifest.

Extracción real cargada mediante `load_manifest('cascante')` y
`load_portal_adapter(manifest)`, con `capture_dir='evidence/captures'`, invocando
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **2 registros, 2 PDF**.
El control compartido de entidades los reconoce como expedientes, con cero
entidades desconocidas y sin inferir concesión de licencia.

Evidencia local en `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/captures/` y capturas de descubrimiento en `evidence/`. La validación
incluye URLs, fecha de ejecución, cantidad real y limitaciones. No se versiona
la evidencia. No se modifica código compartido ni dependencias.
`schedule.enabled=false`; sin ejecución de pipeline global, publicación ni DB.
