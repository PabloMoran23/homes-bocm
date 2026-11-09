# Deba (Gipuzkoa), INE 20029

Verificación real: 2026-11-09. Un solo adaptador municipal, cobertura parcial,
sin programación automática, licencias ni geocodificación artificial.

## Descubrimiento y fuentes oficiales

- [Normas Subsidiarias](https://www.deba.eus/es/ayuntamiento/normativa-municipal/normas-subsidiarias/):
  inventario municipal vivo, HTTP 200. Contiene documentación general y secciones
  desplegables Deba, Itziar y Lastur con planeamiento de desarrollo y gestión.
  El HTML servido incluye las secciones cerradas; no hace falta interacción.
- [Urbanismo](https://www.deba.eus/es/ayuntamiento/departamentos/urbanismo/):
  HTTP 200, enlaza normativa y formularios de obra mayor/menor y actividades.
  Son solicitudes e impresos reutilizables, no licencias concedidas.
- [Planes y proyectos](https://www.deba.eus/es/ayuntamiento/proyectos/): HTTP 200,
  inventario mixto de planes sociales, documentos estratégicos y proyectos físicos
  (Centro de Día, pasarela Sasiola, reurbanización Osio/Astillero, entre otros).
  Se ha investigado pero queda fuera de esta primera cobertura de planeamiento;
  no se clasifican indiscriminadamente todos sus enlaces como proyectos.
- [Tablón](https://www.deba.eus/es/actualidad/avisos/): HTTP 200 pero la respuesta
  examinada muestra «Cargando». No se extraen anuncios ni noticias como actuaciones.

Las capturas `evidence/discovery-*.html` conservan los tres últimos resultados.
Las fuentes de cada instrumento y sus capturas están en `evidence/sources.json`.
No se usa un artículo aislado como inventario ni se consulta un servicio privado.

## Cobertura implementada

Se recorren **todos** los enlaces no vacíos de las listas de las tres secciones
territoriales del inventario, excluyendo expresamente convenios de concertación.
Se extraen **12 instrumentos reales y 303 enlaces documentales agrupados**:

- Deba: PER del casco histórico, PERI Amillaga y su modificación, PEOU Osio,
  plan parcial Elizburu y su modificación, PAU Miramar (7).
- Itziar: PER del casco histórico (1).
- Lastur: formulación del PEOU A.U.21, plan especial Duquesa/Urkulu,
  PAU A.U.21 y reparcelación A.U.21.2 (4).

Cada ficha HTML aporta todos sus enlaces documentales, sin un máximo arbitrario.
Los planos, memorias, fichas y publicaciones oficiales no generan actuaciones
adicionales. Las modificaciones expresamente individualizadas sí son instrumentos
separados del plan original. Los enlaces repetidos se deduplican por URL.
El PDF de modificación de Elizburu está directamente enlazado desde el inventario:
se descarga y se verifica su firma `%PDF-`, HTTP 200. Las otras 11 fichas HTML y
el inventario también devuelven HTTP 200 en la extracción real.

Quedan fuera las NNSS generales y sus anexos, modificaciones fuera de las tres
secciones, convenios, ordenanzas y reglamentos, además del inventario mixto de
Planes y proyectos. En particular, el acuerdo adicional de Amillaga situado bajo
«Reglamentos» no se incorpora. No se afirma cobertura municipal completa,
vigencia consolidada de todos los instrumentos, ni ejecución de obras.

## Procedencia, fechas y disponibilidad

El frontend publica algunos href internos `http://backend:8080/Plone/...`.
No se accede a ese servidor: se sustituye únicamente ese prefijo exacto por
`https://www.deba.eus/`, manteniendo la ruta y `href_publicado` original.
La sustitución se ha comprobado con el PDF de Elizburu; no implica que todos los
otros archivos sean accesibles. Las URLs de documentos proceden del inventario o
de la ficha indicada en `source_url`; no son documentos inventados.

Las otras 302 referencias documentales se conservan con `access_status: not_checked`:
no se afirma haber descargado cada una. Hay rutas heredadas y contenido técnico
sin enlace en el PAU y la reparcelación de Lastur; se retienen los documentos
administrativos disponibles. Algunas fichas ofrecen PDF y DWG; otras enlazan
publicaciones de `ssl4.gipuzkoa.net`. Se conservan también enlaces documentales HTML.

`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas. Los títulos de
certificados/resúmenes pueden contener varias fechas de acuerdos distintos; se
conservan literalmente a nivel documental, sin adjudicarlas a todo el instrumento.
No se toma la fecha de rastreo, la ruta del BOG ni el nombre del PDF como fecha
municipal de publicación, acuerdo, aprobación o concesión. No se deduce la fase
actual de la existencia de un documento de aprobación inicial o definitiva.

## Paginación, errores y actualización

El inventario revisado es una página sin paginación. El parser falla al detectar
controles de paginación o enlaces de siguiente, para evitar un resultado truncado.
También falla ante cambio de título/secciones, instrumento desconocido, inventario
vacío o ficha sin documentación enlazada. Un error de red/HTTP impide sustituir la
instantánea previa. `update_proyectos` repite la instantánea completa del ámbito;
no mantiene un histórico de versiones ni interpreta desapariciones como bajas.

## Geometría y clasificación compartida

`geometry_status: unavailable`, `publication_ready: false`. Hay planos PDF/DWG,
pero no se ha verificado geometría vectorial asociada a estos instrumentos ni un
CRS utilizable. No se sustituyen por centroides, coordenadas inventadas ni jitter.

La extracción mediante el cargador de adaptadores ejecuta además la política
compartida de entidades: los 12 quedan `pendiente / insufficient_identity_evidence`
y el informe señala `adapter_incident / unknown_entity_spike`. La fuente acredita
instrumentos con documentación, pero no proporciona en las listas una referencia
administrativa que satisfaga esa política. No se inventa un número de expediente
para franquearla. Esta limitación impide considerar la salida apta para publicación;
requiere revisión independiente. El scraper y sus evidencias siguen siendo reales.

## Reproducción y validación local

Runtime exigido: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_deba -v
```

Cinco pruebas offline: identidad/deduplicación y fechas nulas; agrupación documental
y procedencia original; rechazo de paginación y cambios de contenido; preservación
de salida ante error; carga de manifest y licencias deshabilitadas.

Extracción real reproducible desde la raíz del repositorio:

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter
manifest = load_manifest('deba')
manifest.portal.config['evidence_dir'] = 'evidence'
result = load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

`evidence/validation.json` recoge recuento real, fuentes, limitaciones y resultado
de la política compartida. `evidence/proyectos.jsonl` contiene los 12 instrumentos;
`sources.json` relaciona las 13 respuestas con sus capturas y hashes SHA-256.
Las evidencias son locales, ignoradas por Git. Solo se añaden los cuatro archivos
fuente solicitados; sin dependencias nuevas, cambios compartidos ni publicación.
