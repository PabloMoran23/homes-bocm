# Tafalla — Navarra — INE 31227

Verificado el 2026-11-07 con peticiones HTTP reales. Adaptador único:
`municipio.adapters.tafalla:TafallaAyuntamientoAdapter`.

## Descubrimiento y alcance

Inventario oficial actual de la web municipal:
https://www.tafalla.es/ayuntamiento/normativa/normativa-urbanistica/

Se descubren y recorren dos colecciones de instrumentos, no noticias ni
anuncios de contratación:

- [PERI Centro Histórico](https://www.tafalla.es/ayuntamiento/normativa/normativa-urbanistica/peri-centro-historico/):
  67 PDFs repartidos entre Marco y Memoria (8), Normativa (20) y Planos (39).
  Las tres páginas se descubren desde la colección y se recorren completas.
- [Plan de movilidad urbana sostenible](https://www.tafalla.es/ayuntamiento/normativa/normativa-urbanistica/plan-de-movilidad-urbana-sostenible/):
  19 PDFs de memoria, gráficos y anejos en la propia página.

Resultado en vivo: **2 registros reales, 86 enlaces documentales**. Cada colección
produce un solo instrumento. Los PDFs conservan título, URL y página(s) de
procedencia; los enlaces duplicados y fragmentos no producen nuevos registros.
Los identificadores derivan de la URL estable de la colección.

Se descargó una memoria de cada instrumento (HTTP 200, firma PDF comprobada),
con capturas locales y texto de sus primeras tres páginas. La del PERI identifica
el Plan Especial de Reforma Interior del Centro Histórico de Tafalla, abril de
2011. La del PMUS identifica el documento final municipal, octubre de 2010.
Son fechas documentales mensuales, **no acuerdos ni publicaciones**; el adaptador
no las convierte en fechas de aprobación. La extracción inventaría los enlaces,
no descarga ni interpreta automáticamente los 86 PDFs.

## Otras fuentes oficiales examinadas y exclusiones

https://www.tafalla.es/transparencia/informacion-sobre-ordenacion-territorial-urbanismo-medio-ambiente-y-vivienda/
remite al registro autonómico
https://administracionelectronica.navarra.es/SIUN_Consulta/Index.html#/instrumentos
indicando buscar TAFALLA. La página inicial SIUN responde 200 y es una aplicación
Angular; no se ha implementado su consulta de expedientes. La normativa vigente
municipal también remite al antiguo `http://siun.navarra.es/Resultados.aspx?muni=227`.
El adaptador **no representa el PGOU completo, sus modificaciones ni el histórico
SIUN**, y no afirma vigencia jurídica de las versiones documentales del PERI/PMUS.

https://www.tafalla.es/web/urbanismo-obras-publicas-y-medioambiente/planes-de-ordenacion-urbana-y-convenios-urbanisticos/
contiene categorías genéricas, sin expedientes o documentación concretos en su
contenido principal; no se genera un registro por esas categorías.

La colección SUD´EAU del inventario contiene un diagnóstico ambiental y anejos;
se excluye al no verificar aquí un proyecto físico de obras. El catálogo de la
sede https://sedeelectronica.tafalla.es/catalogoservicios.aspx ofrece solicitudes
y declaraciones de urbanismo: no acredita concesiones. Licencias deshabilitadas.

## Fechas, cartografía y cobertura

`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` quedan nulos:
las páginas leídas no acreditan esas fechas ni una fase jurídica. No se usa la
fecha de descarga, el año del directorio WordPress o la portada de una memoria
como fecha de acuerdo/publicación.

`geometry_status: unavailable`. Se retienen todos los planos PDF municipales,
pero no se ha verificado una capa vectorial vinculada por expediente o geometría
extraíble. La página de transparencia enlaza además el visor de riesgos de
inundación CHE y PLINUR: no son geometrías de estos instrumentos. No se asigna
centroide municipal ni se vectorizan planos. `lat`, `lon`, `geometry` nulos y
`publication_ready: false`.

La cobertura es parcial y documental. Una futura ampliación a SIUN requiere otro
trabajo de descubrimiento, sin interpretar estas dos colecciones como censo
exhaustivo. La programación automática está deshabilitada y no hay jitter.

## Recorrido y validación reproducible

No hay paginación en las seis páginas del recorrido verificado. Ante controles
Siguiente/next, rel=next, page-numbers o rutas /page/, el adaptador falla para
revisar el recorrido antes de aceptar una salida parcial. Descubre todas las
subpáginas dentro de cada colección, con conjunto de visitadas; cualquier límite
de tamaño o recorrido se convierte en error, nunca en truncamiento silencioso.
También falla si desaparece alguna colección, cambia su título, hay redirección,
contenido vacío o desaparecen sus documentos. Se escribe la salida sólo después
de completar ambas colecciones; update vuelve a leer la instantánea completa.

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_tafalla -v` — **5 pruebas pasan**.
Comprueban el alcance, rechazo de paginación, agrupación/deduplicación,
procedencia, fechas y geometría desconocidas, estabilidad de IDs, conservación de
salida previa ante fallo, manifest y licencias deshabilitadas.

Extracción real desde el workspace:

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.tafalla import TafallaAyuntamientoAdapter
m = load_manifest('tafalla')
a = TafallaAyuntamientoAdapter(m.slug,
    {**m.portal.config, 'capture_dir': 'evidence/captures'}, m.portal.base_url)
result = a.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Evidencias locales, fuera de los cuatro fuentes entregados:
`evidence/proyectos.jsonl`, `evidence/validation.json` (live_records=2,
source_urls, limitations, resultados y muestras PDF), HTML de descubrimiento,
HTML del recorrido en `evidence/captures/`, dos memorias PDF y sus textos.
No se han usado credenciales ni servicios de producción o publicación.
