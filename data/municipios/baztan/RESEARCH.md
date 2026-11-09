# Baztan — INE 31050, Navarra

Investigación y extracción en vivo: 2026-11-08. Python utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales descubiertas

- [Transparencia municipal: ordenación y urbanismo](https://www.baztan.eus/es/transparencia/informacion-sobre-ordenacion-territorial-urbanismo-medio-ambiente-y-vivienda/).
  Enlaza el [listado de planeamiento](https://www.baztan.eus/wp-content/uploads/2021/07/OT-y-PUM.-Listado-y-enlaces.-PORTAL-TRANSPARENCIA-1.pdf).
  Es un PDF alojado en julio de 2021, con instrumentos y fechas definitivas hasta
  2019, además de un POT supramunicipal y ordenanzas. No constituye un registro
  actualizado de todas las actuaciones. Se conserva como descubrimiento, pero
  no se ingiere ni se atribuye su contenido íntegro a proyectos municipales.
- [Baztan Hobetzen](https://baztanhobetzen.baztan.eus/): subdominio municipal
  dedicado al Plan Especial de Actuación Urbana, con navegación bilingüe.
  La [memoria del proceso participativo](https://baztanhobetzen.baztan.eus/wp-content/uploads/2024/02/8-memoria-proceso-participativo.pdf)
  identifica el sitio como herramienta de difusión municipal del PEAU.
- [Documentación en castellano](https://baztanhobetzen.baztan.eus/baztan-hobetzen-cast/resultados/):
  inventario estructurado de documentos vinculados al PEAU de los Cascos de Baztan.
  Es la fuente del adaptador; no se usa un anuncio de contratación ni una noticia
  aislada como sustituto de un proyecto.

## Cobertura y semántica

Se extrae **un instrumento real**, el Plan Especial de Actuación Urbana de los
Cascos de Baztan. Sus **15 documentos** se agrupan en el mismo registro: memoria
participativa, memorias informativa y justificativa, normas generales y particulares,
planos, material de exposición pública, diagnóstico/anteproyecto y presentación inicial.
Se retiene título, URL y sección de procedencia de cada documento. Se deduplican
URL y fragmentos; los documentos y las versiones no generan proyectos adicionales.
El ID permanece estable aunque cambien los documentos.

La sección «FASE 3: Documento de Aprobación Inicial – Exposición Pública» se
conserva como etiqueta documental, sin convertirla en una fase jurídica actual.
La página contiene también documentación de fases anteriores. No se acredita
aprobación definitiva ni ejecución de obras. No se deducen fechas de publicación,
acuerdo o aprobación de las rutas de subida, de fechas de buscadores o del plazo
de alegaciones. Los campos de fecha se omiten.

Cobertura deliberadamente parcial: solo este inventario documental, no el conjunto
del planeamiento municipal, sus modificaciones, todas las obras ni licencias concedidas.
Las licencias están deshabilitadas y sus métodos producen un archivo vacío.
No se extraen solicitudes, formularios, anuncios de licitación o presupuestos como
si fueran concesiones o proyectos acreditados.

## Paginación, fallos y actualización

La página documental es única y no muestra paginación. Se recorre todo su contenido,
sin limitar el número de documentos. Si aparecen enlaces de paginación, `rel=next`
o contenedores de paginación, el adaptador falla explícitamente para exigir revisión.
También falla ante desaparición de la identidad del plan, de sus categorías documentales
esenciales, redirecciones o procedencia documental inesperada. La actualización vuelve
a leer el inventario completo; no existe una fecha fiable para usar como watermark.

## Geometría y validación

Los planos son documentos PDF; no se ha verificado una geometría vectorial vinculada
al instrumento. No se generan coordenadas ni se sitúa el proyecto en el ayuntamiento.
`geometry_status: unavailable`, `publication_ready: false`,
`geocode.jitter_missing: false`, `schedule.enabled: false`.

Tres pruebas unitarias verifican agrupación/deduplicación, procedencia, ausencia de
fechas y coordenadas inventadas, rechazo de paginación/contenido incompleto, resolución
del manifest y contratos de extracción/actualización/licencias.

Validación local reproducible:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_baztan -v
```

Se ejecutó `BaztanAyuntamientoAdapter.backfill_proyectos` contra la fuente real.
`evidence/proyectos.jsonl` contiene el registro; `evidence/validation.json` recoge
recuento, fuentes, limitaciones y resultados de comprobación HTTP de los documentos.
Se conservan capturas HTML, el listado municipal PDF, su texto y una muestra PDF
del instrumento bajo `evidence/`. Las evidencias son locales y no forman parte de
los cuatro archivos fuente. No se utiliza publicación, bases de datos ni despliegue.
