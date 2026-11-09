# Murchante — INE 31176, Navarra

Revisión y extracción HTTP real: 2026-11-09. Adaptador municipal único, limitado
al inventario de anuncios vigentes del tablón oficial y a sus edictos adjuntos.

## Descubrimiento de fuentes

- Web oficial: https://www.murchante.es/ (HTTP 200). Su cabecera enlaza la sede
  https://murchante.sedipualba.es/. La navegación ofrece Información Municipal,
  Trámites y Gestiones y Video Acta Digital; no ofrece un registro municipal
  completo de proyectos directamente en la portada.
- Inventario actual utilizado: https://murchante.sedipualba.es/tablondeanuncios/
  (HTTP 200), opción «Anuncios publicados», filtro «Todas las áreas», sin búsqueda.
  Se observaron 25 anuncios y ninguna paginación, ni controles para avanzar.
  Las filas contienen enlace de detalle, intervalo de exposición y título.
  Se recorren todas las filas; no se fija un ID de anuncio ni un límite de filas.
  Si aparecen controles de paginación, el parser falla explícitamente; no entrega
  una primera página como si fuera el inventario completo.
- Inventario auxiliar de páginas WordPress:
  https://www.murchante.es/wp-json/wp/v2/pages?per_page=100 respondió con las
  páginas municipales de navegación y servicios. Sólo se usó para descubrimiento;
  no es un catálogo de instrumentos ni se extraen registros de sus noticias.
- El edicto enlaza el apartado 10.5 del portal de transparencia:
  https://transparencia.animsa.es/P3117600A. Su HTTP 200 devuelve una aplicación
  Blazor sin contenido de inventario en el HTML. Se conserva la captura, pero
  no se afirma haber recuperado sus documentos técnicos ni recorrido sus datos.
- La web ofrece formularios y catálogo de trámites. No se verificó un registro
  de licencias concedidas: licencias deshabilitadas y métodos con salida vacía.
  No se convierten convocatorias, contratos, órdenes fiscales o noticias generales
  en proyectos ni en licencias concedidas.

## Registro real obtenido

Una modificación estructurante del Plan General Municipal en **las zonas A y B
del SGEQAP del polígono 3, paraje de Campo Bajo**, expediente **286469Z**:

- Detalle descubierto en el inventario:
  https://murchante.sedipualba.es/tablondeanuncios/anuncio.aspx?id=28349
- Edicto oficial adjunto, descubierto en ese detalle:
  https://murchante.sedipualba.es/tablondeanuncios/documento.aspx?id=67294&modo=guardar
- Acuerdo del Pleno de **2026-11-05**: realizar **nueva información pública**.
  No es una aprobación definitiva del instrumento. `fecha_acuerdo` recoge ese
  acuerdo; `fecha_aprob` permanece nula.
- Publicación en el tablón **2026-11-09**, contrastada entre inventario y detalle.
  Intervalo mostrado en el tablón: hasta **2026-12-09**, guardado como
  `fecha_fin_exposicion_tablon` dentro de `avisos`.
- El PDF dice que el mes de información pública se computa desde la publicación
  en el BON. No se verificó esa fecha del BON y no se usa el final del intervalo
  del tablón como plazo jurídico de alegaciones. La firma del alcalde tampoco
  sustituye la fecha del acuerdo.

El parser exige referencia de expediente, párrafo del acuerdo y ámbito del
instrumento en el texto del edicto. El título no procede sólo del anuncio genérico.
El PDF tiene una etiqueta lateral «SELLO» entre dos líneas: se elimina esa etiqueta
independiente al interpretar el título; la descripción conserva el texto extraído.
Se conserva la URL de cada documento y la del aviso que lo publicó. Los avisos y
adjuntos del mismo expediente se agrupan en un único registro, con todas sus URLs.
Una referencia incompatible, cambio de formato, ausencia de edicto o inventario
vacío exige revisión y provoca error antes de reemplazar la salida anterior.

## Cobertura y geometría

Cobertura **parcial**: sólo anuncios vigentes de nueva exposición pública de
modificaciones estructurantes del PGM, con el patrón documental verificado.
No representa todos los instrumentos, todas las fases de tramitación, un histórico
del tablón, todas las obras municipales ni el inventario de transparencia.
Campo Bajo no se confunde con otras modificaciones del PGM (p. ej. Campo Alto).
No se vincula por semejanza de títulos una noticia antigua o una convocatoria.

El adjunto es un edicto administrativo, no el proyecto técnico completo. Remite al
portal de transparencia, cuyo contenido no se ha recuperado. No se verificó una
capa vectorial ni geometría vinculable al expediente: `geometry_status=unavailable`,
`lat`, `lon` y `geometry` nulas, `publication_ready=false`. No se usan centroides,
coordenadas inventadas ni jitter.

## Implementación y validación

Se usa el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Dependencias ya presentes: requests, BeautifulSoup, PyYAML y ejecutable de sistema
`/usr/bin/pdftotext` (extracción de texto PDF, sin instalación ni OCR).

Pruebas:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_murchante -v
```

**7 pruebas pasan**: filtrado de formularios/contratación, deduplicación,
rechazo de paginación y fuentes inesperadas, documentos con procedencia,
contraste de fechas, separación de acuerdo/publicación, agrupación de avisos,
contrato del adaptador, salida anterior intacta ante fallo y carga del manifest.
Las fixtures sintéticas no contienen los IDs reales del registro extraído.

Extracción real mediante el cargador normal, sin orquestadores ni publicación:

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter
manifest = load_manifest('murchante')
manifest.portal.config['capture_dir'] = 'evidence'
adapter = load_portal_adapter(manifest)
result = adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Resultado: **1 registro real**, 1 edicto PDF; política de entidades: 1 expediente,
0 desconocidos. Evidencias locales en `evidence/proyectos.jsonl`,
`evidence/validation.json`, inventario y detalle HTML, PDF y texto del PDF.
La extracción actualiza una instantánea vigente; no mantiene histórico ni infiere
bajas. `update_proyectos` hace la misma lectura completa y no usa cursor de estado.

Manifest: municipio Murchante, provincia Navarra, INE `'31176'`,
`schedule.enabled=false`, `licencias.enabled=false`,
`geocode.jitter_missing=false`. Sin cambios compartidos ni de dependencias.
