# Teror — INE 35027, Las Palmas, Canarias

Investigación y extracción real: 7 de noviembre de 2026. Se revisaron primero `municipio/adapters/portal.py`, el cargador/esquema de manifiestos, el registro de adaptadores y los ejemplos Chipiona y Hernani. Se implementa únicamente el adaptador de Teror, sin cambios compartidos ni dependencias nuevas.

## Fuentes oficiales y alcance

- [Urbanismo del Ayuntamiento](https://teror.es/urbanismo/): inventario de entrada; el scraper descubre sus enlaces P.G.O Supletorio y PEPRI dentro del artículo municipal.
- [Plan General de Ordenación Supletorio de Teror](https://teror.es/plan-general-de-ordenacion-supletorio-de-teror/): página documental con 141 enlaces PDF distintos. Incluye índices, memorias, normativa, información ambiental, planos y estudio de movilidad. Todo pertenece a un único instrumento: no se convierten las fichas o propuestas de movilidad en obras independientes ni se afirma su ejecución.
- [PEPRI](https://teror.es/oficina-tecnica-pepri/): página documental con 13 enlaces PDF distintos, agrupados en un segundo instrumento. Conserva además el enlace legado «Catalogación de edificios protegidos» como enlace relacionado; no se extraen fichas de ese catálogo.

Resultado vivo: **2 registros, 154 enlaces PDF**, más el enlace relacionado del catálogo. Las dos páginas presentan listas completas en el artículo, sin paginación observada. No hay límite de número de documentos. El parser falla ante controles de paginación detectados y exige ambos enlaces revisados; no devuelve silenciosamente un subconjunto si desaparece una fuente. La extracción es una instantánea completa, también en `update_proyectos`; no se modifica un estado incremental con fechas desconocidas.

Se examinaron también [Oficina Técnica](https://teror.es/oficina-tecnica/) y los resultados oficiales de [Trámites](https://teror.es/tramites-de-la-oficina-tecnica/) y [Transparencia](https://transparencia.teror.es/t/categorias). Los modelos de solicitud no constituyen licencias concedidas. El enlace que el portal municipal presenta hacia `https://transparencia.teror.es/t/p/1706-plan-general-de-ordenacion` respondió **HTTP 404**, por lo que no se utiliza como inventario. Esto no bloquea las dos fuentes municipales documentales accesibles. No se usan noticias ni anuncios de contratación como registros de proyectos.

## Semántica y limitaciones

Cobertura parcial: exclusivamente estos dos instrumentos publicados y enlazados desde Urbanismo. No es un registro exhaustivo de planeamiento, obras ni licencias; tampoco certifica vigencia. El PGO lleva el rótulo literal «Aprobación definitiva», conservado en `estado_documental_fuente`, sin convertirlo en fecha o fase jurídica verificada. No se deducen fechas de publicación, acuerdo o aprobación a partir de rutas `/2010/03/`, metadatos CMS, títulos de archivos ni fechas de documentos parciales. No se asignan coordenadas. `publication_ready=false`, `geometry_status=unavailable`.

Cada documento conserva título, URL y página de procedencia. Se resuelven los enlaces relativos con la URL real de la página, sin corregir por conjetura las rutas antiguas `images/stories/...`; pueden estar rotas. No se ha comprobado la disponibilidad de todos los enlaces. La disponibilidad por documento permanece `not_checked` en los registros; las dos comprobaciones puntuales están en la validación, sin extender su resultado al resto del inventario.

Muestras comprobadas: normativa del PGO (`Normativa%20PGOS%20AP%20DEF.pdf`) y memoria del PEPRI (`MEMORIA.pdf`), ambas en `https://teror.es/wp-content/uploads/2010/03/`, respondieron HTTP 200, `application/pdf` y firma `%PDF-`. Se guardaron únicamente los primeros 1024 bytes de cada muestra, sin descargar todo el inventario.

El manifiesto identifica Teror, provincia de Las Palmas, INE `35027`, y desactiva licencias, programación y jitter. La ausencia del artículo, de documentos, de títulos esperados o de enlaces revisados produce error antes de reemplazar la salida.

## Reproducción y evidencia local

Runtime preinstalado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_teror -v`. Cubren agrupación, aislamiento de instrumentos, procedencia, enlaces relativos, ausencia de fechas/coordenadas inferidas, errores de estructura, paginación, ausencia de truncación, escritura de instantáneas y licencias desactivadas.

Ejecución real desde el workspace, con el mismo runtime:

```python
from pathlib import Path
from municipio.adapters.teror import TerorAyuntamientoAdapter
adapter = TerorAyuntamientoAdapter('teror', config={'capture_dir': 'evidence'})
adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json` (recuento, URLs, limitaciones y comprobaciones HTTP), capturas `urbanismo.html`, `pgo.html`, `pepri.html`, `categorias.html` y muestras `document-0.bin`, `document-1.bin`. Se ejecutó extracción directa, sin publicación, geocodificación, base de datos o despliegue.
