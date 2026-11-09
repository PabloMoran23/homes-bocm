# Benacazón (Sevilla), INE 41015

Investigación y extracción real: 9 de noviembre de 2026.

## Fuente oficial e inventario

La [web municipal](https://www.benacazon.es/es/) incluye PGOU en su navegación.
El [enlace municipal PGOU](https://www.benacazon.es/es/ayuntamiento/pgou/)
redirige al [indicador de planeamiento del portal municipal de transparencia](https://transparencia.benacazon.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00005).
Se ha consultado ese inventario servido actualmente, no una lista precargada ni resultados de buscador usados como registros.

Resultado de `backfill_proyectos`: **2 instrumentos, 53 enlaces documentales únicos**:

- Normas Subsidiarias de Benacazón: 33 documentos bajo la sección municipal NORMAS SUBSIDIARIAS, incluidos certificado, publicación oficial, memorias, normas, planos y estudio ambiental.
- Plan General de Ordenación Urbana de Benacazón: 20 documentos únicos de las secciones Proyecto del PGOU (Información/Ordenación), Aprobación Inicial (planimetría) y BOP. Los planos AVANCE repetidos en varias secciones se mantienen una vez, con todas sus etiquetas y páginas de procedencia.

Los agrupamientos siguen las secciones y directorios documentales del inventario. No se crean actuaciones independientes por plano, memoria o boletín. Los identificadores locales corresponden a esos dos instrumentos, no a números de expediente oficiales.

## Paginación

Las galerías de OpenCMS comparten `pagegalleryfiles-1-1`. NNSS tiene 3 páginas; Información y la planimetría repetida tienen 2; Ordenación se repite sin paginar. Se recorren las páginas 1, 2 y 3 y se fusionan los enlaces.

La ejecución inicial detectó que, al solicitar la página 3, las galerías pequeñas generan un Siguiente=4 aunque Última=2. Las peticiones fuera de rango siguen generando Siguiente=N+1 y repiten contenido. Se interrumpió esa ejecución, se corrigió el rastreo y se repitió la extracción real. El adaptador respeta Última de cada galería; cuando Última es un fragmento, utiliza sus enlaces numerados. No se impone un corte de registros. Un límite de seguridad de 100 páginas provoca error explícito, nunca salida truncada. Un cambio de URL/parámetro de paginación o una página solicitada no servida también provoca error.

## Comprobación documental y semántica

Dos adjuntos se descargaron completos, con HTTP 200, `application/pdf` y firma PDF:

- [Certificado de NNSS](https://transparencia.benacazon.es/export/sites/benacazon/es/transparencia/.galleries/IND-50-/pgou/00a-Exp_Adto-Certif-Resoluc-Aprob-Definitiva.pdf): 120978 bytes; documento escaneado, sin texto extraíble con pdftotext.
- [BOP enlazado por el PGOU](https://transparencia.benacazon.es/export/sites/benacazon/es/transparencia/.galleries/IND-50-/avance-pgou/16.pdf): 344948 bytes; boletín completo número 39, publicado el 16 de febrero de 2007, cuyo sumario y anuncio identifican el PGOU y estudio ambiental de Benacazón. Contiene también otros municipios: no se extraen sus anuncios como proyectos de Benacazón.

La fecha de publicación del boletín no se convierte en fecha de acuerdo o aprobación. El adaptador no analiza fechas del texto documental ni usa fechas del CMS. Omite `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase`. Las etiquetas documentales se conservan literalmente en `secciones_fuente`; las repeticiones de planos AVANCE no demuestran una fase actual.

## Cobertura y límites

Es un inventario documental histórico accesible actualmente, no un registro completo de expedientes, obras activas o planeamiento vigente. No se afirma que estos instrumentos sean los últimos, estén aprobados definitivamente o sigan vigentes. La web municipal también anuncia la [redacción de un PGOM](https://www.benacazon.es/es/actualidad/noticias/LA-REDACCION-DEL-PLAN-GENERAL-DE-ORDENACION-MUNICIPAL-PGOM-EN-PROYECTO/); esa noticia queda fuera de este inventario documental. No se incluyen licitaciones, impresos, noticias ni concesiones de licencias.

No se han descargado ni validado individualmente los 53 PDF: se retienen todos sus enlaces y se comprueban dos muestras. No se extraen geometrías de planos, no se inventan coordenadas ni fechas. `publication_ready=false`, `geometry_status=unavailable`; `schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.

## Verificación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_benacazon -v`

9 pruebas correctas: agrupación y procedencia de duplicados, rechazo de formularios/anuncios ajenos/vacíos, paginación completa y fallo OpenCMS fuera de rango, aislamiento documental, actualización completa, errores de red sin sobrescribir evidencia previa, páginas ignoradas y manifest.

Extracción real mediante `load_manifest('benacazon')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `manifest.portal.config['capture_dir']='evidence'`. El refresco incremental vuelve a recorrer todo el inventario. La anotación compartida de entidades devuelve dos identidades no clasificadas (`unknown`): no se altera esa política ni se presentan como actividad lista para publicar.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json` (live_records=2, URLs consultadas, limitaciones, resultados de pruebas), `inventory-1.html` a `inventory-3.html`, capturas de navegación, dos PDF, textos de comprobación y `document_checks.json`. Sin operaciones de base de datos, publicación o despliegue.
