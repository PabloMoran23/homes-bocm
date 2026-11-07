# Baiona — Pontevedra — INE 36003

Verificación: 2026-11-07. Adaptador exclusivo para los inventarios documentales
municipales de planeamiento. No es un inventario exhaustivo de actuaciones actuales.

## Descubrimiento y fuentes oficiales

Punto de entrada: [Concejalía municipal de Medio Ambiente e Infraestructuras](https://www.baiona.gal/concejalia-de-urbanismo-vivienda-infraestructuras-y-patrimonio/).
La navegación oficial enlaza los tres inventarios siguientes. El adaptador descubre
sus URL en cada ejecución, elimina repeticiones de navegación y exige los tres.

- [Plan General de Ordenación Municipal](https://www.baiona.gal/concejalia-de-deportes-politica-social-y-asociacionismo/plan-general-de-ordenacion-municipal/):
  inventario de memoria, información urbanística, estudio rural, normativa,
  patrimonio, evaluación ambiental y participación. La página indica que el
  documento diligenciado puede solicitarse en el registro municipal.
- [Plan Especial del Conjunto Histórico-Artístico](https://www.baiona.gal/concejalia-de-deportes-politica-social-y-asociacionismo/plan-especial-do-conxunto-historico-artistico/):
  página identificativa que actualmente dice «Área en construcción».
- [Trámites administrativos de Urbanismo](https://www.baiona.gal/concejalia-de-deportes-politica-social-y-asociacionismo/tramites-administrativos-de-urbanismo/):
  exclusivamente sus secciones **PEPCHAB** y **Normativa PXOM** aportan documentos
  a los dos instrumentos. Los formularios de licencia y comunicación previa se
  excluyen: no prueban concesiones ni constituyen proyectos.

Las cuatro páginas respondieron HTTP 200. Resultado real: **2 instrumentos**:
PXOM, con **31 PDF únicos / 32 referencias**, y PEPCHAB, con **1 PDF / 1 referencia**.
Se agrupan todas las partes por instrumento y se conserva la página de procedencia
junto a cada etiqueta original. «2.0 Estudio de Medio Rural» y «3.4 Planos de
ordenación» comparten destino en la propia web: se conserva esa anomalía sin
inventar un plano alternativo. El enlace externo antiguo a SIOTUGA se conserva como
referencia del PEPCHAB, sin presentarlo como un documento específico descargado.

## Semántica y límites

Se extraen instrumentos reales disponibles en el inventario municipal actual,
no proyectos nuevos por cada capítulo. No se asignan fechas de publicación,
acuerdo o aprobación: no se analizan los PDF para determinar esos hechos y la
fecha técnica de una página no acredita aprobación. Tampoco se afirma una fase
jurídica vigente ni que el inventario incluya todas las modificaciones posteriores.
No se extraen anuncios de contratación ni noticias como expedientes.

Las páginas revisadas son inventarios documentales sin paginación. Se procesan
todos sus enlaces PDF pertinentes, sin límite de filas ni selección de primeros
resultados. Si aparecen controles de paginación, falta el contenido principal o
desaparecen las secciones exigidas, la extracción falla antes de sustituir la
salida anterior. La actualización relee íntegramente estas páginas pequeñas.
No recorre el tablón, el registro de licencias, las noticias de obras ni el catálogo
completo autonómico; por tanto la cobertura es parcial.

geometry_status: unavailable

No se ha verificado geometría vectorial vinculada a estos registros. El enlace
municipal al antiguo portal SIOTUGA no acredita por sí mismo una geometría ni un
CRS. El [portal oficial actual SIOTUGA](https://siotuga.xunta.gal/siotuga/urb)
es una posible vía de ampliación; no forma parte de esta extracción. No se
vectorizan planos ni se asignan centroides o coordenadas inventadas.
`publication_ready` es falso en los registros por estas limitaciones.

## Validación reproducible y evidencia local

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_baiona -v
```

Cuatro pruebas pasan: agrupación y procedencia, exclusión de formularios y fechas
inferidas, rechazo de paginación/cambios de estructura, actualización, preservación
de salida ante error y configuración del manifest.

La ejecución real de `BaionaAyuntamientoAdapter.backfill_proyectos` escribió
`evidence/proyectos.jsonl`. `evidence/validation.json` contiene `live_records: 2`,
las URL consultadas, limitaciones y comprobaciones de documentos. Se capturaron
los cuatro HTML y sus URL/estados en `evidence/sources/`. Se descargaron además
el anuncio DOGA del PXOM y la normativa del PEPCHAB: HTTP 200, tipo PDF y firma
`%PDF-` comprobados. No se verificaron las descargas de todos los demás PDF ni se
extrajo su contenido. La evidencia es local y no se incluye en los fuentes.

Manifest: licencias deshabilitadas, programación deshabilitada y
`geocode.jitter_missing: false`. Sin cambios compartidos, dependencias ni publicación.
