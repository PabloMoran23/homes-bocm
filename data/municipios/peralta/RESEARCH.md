# Peralta / Azkoien — INE 31202, Navarra

Verificado el 2026-11-09 con el runtime preinstalado. Un solo adaptador municipal;
extracción de proyectos, no de licencias concedidas.

## Descubrimiento y fuentes oficiales

- https://aytoperalta.com/ — web del Ayuntamiento, dirección en Peralta, Navarra;
  enlaza «Fondos Europeos», sede, tablón y transparencia. Captura `evidence/home.html`.
- https://aytoperalta.com/fondos-europeos/ — inventario municipal «Archivos:
  Proyectos», HTTP 200, cinco entradas en `main#content article`. Es la fuente
  del adaptador; no se usan noticias individuales como semillas.
- https://peralta.sedelectronica.es/board — HTTP 200. Expone anuncios de
  planeamiento, solicitudes de actividad, ordenanzas y otros procedimientos;
  tiene «Mostrar más» mediante Wicket. No se implementa su recorrido y **no se
  incluye ninguna parte del tablón en la cobertura del adaptador**. Captura
  `evidence/board.html`. Una solicitud no acredita una concesión.
- https://peralta.sedelectronica.es/transparency — HTTP 200. La sección «7.
  URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» indica 16 elementos y navegación
  dinámica Wicket. No es una fuente cubierta. Captura `evidence/transparency.html`.

## Cobertura efectiva y procedencia

La ejecución real, mediante `load_manifest` y `load_portal_adapter`, devuelve
**5 proyectos físicos** del inventario municipal de fondos europeos:

| ID municipal WordPress | Actuación | Ficha oficial |
| --- | --- | --- |
| 20302 | Instalación fotovoltaica (82,62KWP) para autoconsumo en el polideportivo municipal | https://aytoperalta.com/fondos-europeos/instalacion-fotovoltaica-8262kwp-autoconsumo-con-excedentes-en-cubiertas-del-polideportivo-municipal/ |
| 19422 | Adecuación ambiental y espacio de interpretación Molino de Agua | https://aytoperalta.com/fondos-europeos/adecuacion-ambiental-y-espacio-de-interpretacion-molino-de-agua/ |
| 19420 | Adaptación al riesgo de inundaciones | https://aytoperalta.com/fondos-europeos/19420/ |
| 19418 | Construcción de Aula Mentor | https://aytoperalta.com/fondos-europeos/19418/ |
| 19416 | Modernización de infraestructura escénica de la Escuela de Música | https://aytoperalta.com/fondos-europeos/19416/ |

Los títulos literales se conservan en JSONL, normalizando únicamente Unicode NFC.
Los IDs proceden de `post-N` en la ficha del tipo `fondos_europeos`: son IDs de
publicación municipal, **no números de expediente administrativo**. Cada ficha
se contrasta con el título descubierto en el inventario. La identidad no depende
del slug legible, ni se inventan expedientes para superar la política de entidades.
La política compartida anota los cinco registros como `unknown`; no están
habilitados para publicación (`publication_ready: false`).

Las cinco fichas tienen `.page-content` vacío. No hay memorias, planos, PDFs ni
fechas visibles. La evidencia es la catalogación expresa del Ayuntamiento como
proyectos, con títulos que describen intervenciones físicas; no acredita aprobación,
adjudicación, concesión de fondos, comienzo ni finalización de las obras. No se
completa su descripción con noticias o inferencias. `fecha`, `fecha_publicacion`,
`fecha_acuerdo`, `fecha_aprob` y `fase` quedan nulos. No se transforma la fecha
de captura, un directorio de uploads ni metadatos técnicos en fecha de aprobación.

`documentos` está vacío en esta extracción. Si aparecen adjuntos PDF/ZIP/Office
en el contenido de una ficha, se agrupan por URL dentro de ese proyecto, con
su página de procedencia; no se generan proyectos por documento. No se afirma
haber descargado documentación que el portal no ofrece.

## Recorrido y límites

El inventario revisado no presenta paginación. El adaptador recorre enlaces
WordPress numerados y siguiente, deduplica páginas y proyectos y mantiene una
instantánea completa de esta fuente. Ante paginación no reconocida, carga dinámica,
100 páginas, un inventario vacío, cambios de ficha, categorías no revisadas o
errores HTTP, falla antes de sustituir la salida; nunca devuelve silenciosamente
las primeras páginas como si fueran el total. `update_proyectos` hace el mismo
recorrido completo y no depende de fechas inexistentes.

Cobertura **parcial**: este inventario de fondos europeos no es el registro completo
de obras, licencias ni planeamiento vigente/histórico de Peralta. No se implementan
SIUN, catastro, contratación ni las publicaciones del BON como inventarios adicionales.
Los métodos de licencias devuelven cero con estado `disabled`.

## Geometría

`geometry_status: unavailable`. El inventario y sus fichas no proporcionan geometrías
ni coordenadas vinculadas a los cinco IDs. No se usa la dirección del Ayuntamiento
como ubicación de las obras, ni centroides, jitter o digitalización inferida. No se
ha verificado un servicio vectorial que relacione estos IDs WordPress con polígonos.

## Validación reproducible y evidencias locales

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_peralta -v
```

Seis pruebas pasan: identidad y campos ausentes, agrupación de adjuntos,
deduplicación, paginación de dos páginas, rechazo de fuentes/categorías inesperadas,
protección de salida previa ante errores, manifiesto y licencias deshabilitadas.
Las pruebas usan fixtures HTML sin red; la ejecución real se realiza por separado.

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter
manifest = load_manifest('peralta')
manifest.portal.config['evidence_dir'] = str(Path('evidence').resolve())
adapter = load_portal_adapter(manifest)
report = adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Resultado real: 1 página de inventario, 5 fichas, 5 registros. Capturas HTML
completas con nombres SHA-256 de URL (16 caracteres) y su correspondencia en
`evidence/validation.json`, que incluye `live_records`, `source_urls`, limitaciones,
hora UTC y resultado de la política compartida. Datos en `evidence/proyectos.jsonl`.
Las evidencias son locales y no se incorporan al código fuente.

`schedule.enabled: false`, `licencias.enabled: false`,
`geocode.jitter_missing: false`. Sin cambios compartidos, dependencias, DB,
publicación ni despliegue.
