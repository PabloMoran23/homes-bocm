# Tocina (Sevilla), INE 41092

Investigación y extracción real: 7 de noviembre de 2026. Adaptador exclusivo de Tocina; no se modifican fuentes compartidas ni dependencias.

## Fuentes oficiales descubiertas

- Portal del Ayuntamiento: https://www.tocina.es/es/index.html . Enlaza el PGOU municipal y el nuevo PBOM.
- Inventario PGOU: https://www.tocina.es/es/ayuntamiento/pgou/ . Contenedor `#cuerpo`, 100 enlaces PDF distintos de `multimedia.dipusevilla.es/tocina/pgou/`. Memorias, normas, catálogo, fichas, planos, anexos, certificados y convenio Azucarera se conservan juntos como el dossier PGOU publicado, sin convertir cada plano o certificado en un proyecto independiente. No se observó paginación en esta página.
- Inventario municipal de transparencia: https://transparencia.tocinalosrosales.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00002/ . Sección ADAPTACION LOUA, `article.documentacion`, documentos en `IND-50-/ADAPTACION-PARCIAL-LOUA/`. Hay dos páginas, parámetro `pagegalleryfiles-2-1`; se recorren todos los enlaces anunciados, incluida la URL explícita de página 1. Nueve documentos de adaptación (memoria y planos) y cuatro de corrección de error material (anuncio, corrección e informes). Los documentos de corrección se agrupan en un instrumento separado de la adaptación.
- Inventario provincial antiguo enlazado por transparencia: https://3web.dipusevilla.es/planeamiento/TOCINA/index.htm . No constituye una fuente adicional del scraper, para evitar duplicar el PGOU.
- Nuevo plan enlazado por la portada municipal: https://nuevoplandetocinaylosrosales.es/ . Página consultada y capturada; contiene un manual de participación y también un enlace de plantilla referido a Peñaflor. No se incorpora al inventario implementado ni se atribuye documentación de otro municipio a Tocina. Cobertura PBOM excluida.

## Extracción y semántica

Resultado vivo: **3 registros y 113 enlaces documentales distintos**, agrupados como PGOU (100), adaptación parcial LOUA (9) y corrección de error material de la adaptación (4). Identificadores estables por instrumento, deduplicación por URL dentro de cada grupo. Cada documento conserva su título, URL original y página de inventario de procedencia. Los enlaces HTTP históricos no se sustituyen por URLs supuestas.

El scraper lee los inventarios en cada ejecución; no precarga registros ni utiliza noticias o anuncios de contratación como actuaciones. La presencia de un anuncio BOP en el dossier de corrección sirve como documentación del instrumento, no como licencia concedida. No se extraen licencias: `licencias.enabled: false`. `update_proyectos` renueva la instantánea completa y no usa un corte temporal que pueda perder documentos.

No se afirma aprobación, vigencia, ejecución ni consolidación jurídica de los instrumentos. Se omiten fechas de publicación/acuerdo/aprobación: ni un certificado titulado con fecha ni la marca temporal del CMS acreditan esos campos para el instrumento completo. No se inventan coordenadas; `geometry_status: unavailable` y `publication_ready: false`. `schedule.enabled: false` y `geocode.jitter_missing: false`.

Cobertura deliberadamente parcial: únicamente estos dos inventarios municipales, sin asegurar todas las modificaciones posteriores, obras, PBOM ni registro histórico de planeamiento. Los documentos no se interpretan íntegramente ni se resuelven sus posibles contradicciones.

## Disponibilidad y fallos explícitos

Las páginas HTML respondieron HTTP 200. Descarga de muestra del anuncio de corrección:
https://transparencia.tocinalosrosales.es/export/sites/tocina/es/transparencia/.galleries/IND-50-/ADAPTACION-PARCIAL-LOUA/ANUNCIO-B.O.P.-CORRECCION-ADAPT.-PGOU.pdf
respondió HTTP 200, `application/pdf`, firma `%PDF-`; se conserva en evidencia.

El PDF de muestra `http://multimedia.dipusevilla.es/tocina/pgou/92pgMI.pdf` agotó 35 segundos de conexión; la comprobación HTTPS equivalente también. El inventario PGOU es accesible, pero no se garantiza acceso a sus ficheros históricos. Los documentos de transparencia sí ofrecen evidencia documental descargable. No se han comprobado individualmente los 113 destinos.

El adaptador rechaza inventarios vacíos, contenedores desaparecidos, familias documentales desconocidas, redirecciones de inventario a otro host y paginación no reconocida. Sigue todas las páginas anunciadas; superar el límite defensivo de 100 páginas provoca error sin escribir resultados parciales. La salida se reemplaza solamente tras completar ambos inventarios.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_tocina -v`: **5 correctas**. Cubren agrupación y deduplicación, procedencia de documentos, ausencia de fechas/coordenadas inventadas, rechazo de cambios estructurales, recorrido de segunda página mediante HTTP simulado, actualización de instantánea e identidad/configuración del manifest.

Extracción real mediante `load_manifest('tocina')`, `load_portal_adapter(manifest)` y `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Se configura `capture_dir` únicamente para guardar evidencia local. Se ejecuta también la anotación de política de entidades del cargador compartido; no se realizan operaciones de base de datos, publicación o despliegue.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML de ambas fuentes y de sus páginas de galería, portada municipal/nuevo PBOM y PDF BOP de muestra. `validation.json` contiene conteo real, URLs recorridas, resultados de pruebas y limitaciones.
