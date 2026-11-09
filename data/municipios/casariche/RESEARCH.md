# Casariche (Sevilla), INE 41026

Investigación y extracción real: 9 de noviembre de 2026. Se revisaron primero
`municipio/adapters/portal.py`, `municipio/manifest.py` y los ejemplos de Chipiona
y Hernani. Se mantiene el contrato de sus cuatro métodos y el esquema existente,
sin cambios compartidos ni dependencias nuevas.

## Fuentes oficiales descubiertas y alcance elegido

- [Inventario documental municipal del PBOM](https://www.casariche.es/?page_id=63413):
  fuente implementada. La página dedicada publica documentación de las fases 0,
  I, II y III del Plan Básico de Ordenación Municipal. Contiene memorias,
  diagnóstico, propuesta y anexos, documentos iniciales estratégicos, resumen
  ejecutivo, evaluación de impacto en salud y cartografía ZIP. No es una noticia
  de contratación ni una mera solicitud de licencia.
- [Indicador 50 del portal municipal de transparencia](https://transparencia.casariche.es/es/transparencia/indicadores-de-transparencia/indicador/50.-Plan-General-de-Ordenacion-Urbana-PGOU/):
  comprobado en vivo y capturado en `evidence/transparencia.html`. Es otra fuente
  documental histórica: adaptación parcial de las NNSS, memoria, normas y planos.
  La página indica un acuerdo de 4 de noviembre de 2011 para esa adaptación;
  **no se traslada esa fecha al PBOM**. Queda fuera del alcance de este scraper.
- [ProCasariche](https://procasariche.casariche.es/): consultado durante el
  descubrimiento; presenta registros de demandantes de suelo residencial e
  industrial. No se consideran proyectos ni licencias concedidas.

Cobertura deliberadamente parcial del municipio: exclusivamente el inventario
documental del PBOM publicado en la página dedicada. No se declara un catálogo
completo de instrumentos, obras, noticias, resoluciones ambientales o licencias.

## Unidad de registro y procedencia

La ejecución produjo **1 instrumento real, 32 URLs documentales únicas y 33
referencias documentales**. Se agrupan todas las fases, memorias, planos y anexos
del mismo PBOM en un registro estable `casariche-pbom-63413`. El anuncio de consulta
previa es documentación de ese instrumento; no constituye un proyecto adicional.
Los formularios externos de participación y los enlaces para compartir se excluyen.

Cada documento conserva la página de procedencia, URL original publicada y las
referencias con su título, fase documental y texto del enlace. Para transporte se
ofrece la URL HTTPS equivalente a los enlaces HTTP del portal, manteniendo estos
últimos en `url_fuente`. El portal enlaza el mismo PDF para «MEMORIA» y «ÍNDICE
DOCUMENTACIÓN GRÁFICA» de fase II: se conserva un documento con ambas referencias,
sin inventar un archivo corregido. Los cuatro enlaces de propuesta/anexos son
documentos separados dentro del mismo instrumento, con sus etiquetas originales.

El inventario observado es una página completa, sin paginación identificada.
No hay límites de cantidad ni cortes de resultados. Si aparecen controles de
paginación, desaparece el artículo o faltan documentos/títulos/fases, el adaptador
falla antes de reemplazar la salida, para exigir revisión de la cobertura.
`update_proyectos` vuelve a leer el inventario completo y recoge sus cambios.

## Fechas, estado y localización

No se infieren fechas de publicación a partir de rutas de subida, ni fechas de
acuerdo/aprobación de firmas o sellos de entrada. El PDF de muestra identifica
«FASE III: DOCUMENTO DE AVANCE» y una fecha documental de 23 de mayo de 2025; su
sello de entrada también tiene esa fecha. Eso no demuestra la aprobación del
plan ni la fecha de publicación de la página. Por ello el registro no asigna
fechas ni estado jurídico actual. `fase_documental` describe únicamente la
sección del inventario a la que pertenece cada referencia.

Sin coordenadas ni geometría deducidas. `publication_ready: false` y
`geometry_status: unavailable`. El manifest identifica Sevilla e INE 41026,
desactiva programación, jitter y licencias. No se ha verificado un registro de
licencias concedidas; los métodos de licencias producen salida vacía explícita.

## Verificación reproducible

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_casariche -v`: **6 correctas**. Cubren la
agrupación de documentos y alias, procedencia, exclusión de formularios/noticias,
ausencia de fechas/coordenadas inventadas, rechazo de paginación/cambios de
estructura, manifest, licencias desactivadas y conservación de salida ante error
HTTP.

Extracción real, sin pipeline de publicación:

```python
from pathlib import Path
from municipio.adapters.casariche import CasaricheAyuntamientoAdapter

adapter = CasaricheAyuntamientoAdapter(
    'casariche', {'capture_dir': 'evidence'})
adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/pbom.html`, `evidence/transparencia.html`,
`evidence/resumen_ejecutivo.pdf` y texto extraído de sus tres primeras páginas.
Se descargó íntegramente el
[resumen ejecutivo](https://www.casariche.es/wp-content/uploads/2025/07/40.-RESUMEN_EJECUTIVOf.pdf):
HTTP 200, `application/pdf`, 11.037.310 bytes y cabecera `%PDF-` válida; el texto
confirma municipio, instrumento y carácter de avance. No se validaron
individualmente los restantes 31 destinos documentales ni se interpretó el ZIP.

Una petición exploratoria sin User-Agent de navegador recibió HTTP 403. Las
peticiones posteriores y la ejecución real del adaptador, con User-Agent
declarado, respondieron correctamente. No se eluden autenticación ni controles
de acceso. Los errores HTTP se propagan; no se sustituyen por registros prefijados.
