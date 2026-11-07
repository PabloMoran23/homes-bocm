# Mula — Murcia — INE 30029

Verificación en vivo: 2026-11-07. Adaptador de inventarios oficiales, cobertura
parcial y `publication_ready: false`. No registro de licencias concedidas.
Se revisaron primero `portal.py`, `manifest.py`, el registro de adaptadores y los
ejemplos de Chipiona y Manlleu. No se modifican contratos ni dependencias comunes.

## Fuentes y alcance

Las seis páginas siguientes respondieron HTTP 200 y son el conjunto completo de
páginas procesadas por esta implementación:

- https://mula.es/web/urbanismo-y-patrimonio/ — índice municipal de Urbanismo y
  Patrimonio. Enlaza los inventarios y un documento específico del **Proyecto de
  obras de excavación y protección de acceso al Castillo de Mula** en Drive.
  Ese proyecto constituye un registro, distinto del Plan Director del Castillo.
- https://mula.es/web/urbanismo-y-patrimonio/plan-general-municipal-de-ordenacion/
  — un PGMO, 22 enlaces documentales o de consulta: normativa, memoria, programa,
  estudios, avance y cartografía. La página dice «PGMO actualmente en vigor».
  Repite también el Plan Especial; esa sección se excluye aquí para evitar
  duplicarlo. Las fechas de sesiones de 2012-06-28 y 2014-11-27 se extraen
  únicamente de los títulos que las expresan, a nivel de documento. El año 1998
  del encabezado y los años de los estudios no se convierten en fechas de aprobación.
- https://mula.es/web/urbanismo-y-patrimonio/modificaciones-pgmo/
  — tres grupos de acordeón completos: modificaciones 24, 25 y 26. Se conservan
  respectivamente 4, 7 y 4 enlaces: proyecto/memoria, acuerdos, anuncios BORM,
  documentación ambiental y antecedentes. Los documentos históricos de la 25
  permanecen en ese instrumento. No se interpreta un anuncio como otro proyecto.
- https://mula.es/web/urbanismo-y-patrimonio/plan-especial-proteccion-revitalizacion-conjunto/
  — un Plan Especial, cinco documentos de memoria, catálogo, planos, normas y
  etapas/estudio económico.
- https://mula.es/web/urbanismo-y-patrimonio/modificacion-puntual-del-plan-parcial-el-arreaque/
  — un instrumento con cinco documentos: BORM, acuerdo de Pleno, proyecto, anexo
  e informe ambiental. El texto municipal del acuerdo conserva Urban/2019/0003.
- https://mula.es/web/urbanismo-y-patrimonio/plan-director-mula/
  — un Plan Director del Castillo, cinco enlaces a análisis, propuestas, anexos
  y planimetría ZIP. No implica una aprobación ni ejecución de todas sus propuestas.

Los enlaces antiguos `/web/plan-general-municipal-de-ordenacion/` y
`/web/modificaciones-pgmo/`, presentes en el índice, redirigen a los destinos
anteriores. El adaptador solicita directamente las URLs canónicas verificadas.

## Fuentes adicionales inspeccionadas y límites

- https://mula.es/web/planos-pgmo/ — hojas PDF e imágenes del PGMO. Se conserva
  el enlace del índice cartográfico en el instrumento; las hojas individuales no
  se descargan ni se convierten en proyectos. Tampoco se extrae geometría de los
  servicios de mapas CARM enlazados desde el PGMO.
- https://mula.es/web/urbanismo-y-patrimonio/plan-municipal-de-vivienda/
  — información y formularios de demanda/rehabilitación; no son obras ni licencias
  concedidas. No se emiten registros a partir de esos formularios.
- El índice contiene también catastro, servicios, inventario patrimonial y un
  análisis de planeamiento de 2019. No se presentan como proyectos adicionales.
  No se hace una búsqueda exhaustiva de noticias, contratación, sede o BORM.

Las páginas seleccionadas son inventarios estáticos sin paginación observada.
Se recorren todos los grupos y todos sus enlaces, sin límite de registros. Si
aparece paginación, desaparece el contenido esperado, hay una redirección distinta,
un grupo desconocido o un identificador duplicado, se falla antes de escribir la
salida completa. `update_proyectos` refresca la misma instantánea íntegra.

La procedencia documental es el enlace y título publicados por el Ayuntamiento,
con `source_url` en cada documento. No se descargan los PDF ni se verifica su
contenido, accesibilidad externa o vigencia jurídica. Los enlaces Drive conservan
sus parámetros, incluidos los `resourcekey`. La web reutiliza algún destino en
documentos de instrumentos distintos (por ejemplo el estudio económico); se
conserva esa atribución publicada sin corregirla ni inventar destinos.

No se deducen fechas desde rutas de subida, años de URLs BORM ni actualización
de página. Las fechas generales de publicación, acuerdo y aprobación permanecen
nulas: no se traslada la fecha de una pieza al instrumento entero. No se afirma
una fase de aprobación a partir del mero tipo de instrumento. Coordenadas y
geometría permanecen nulas; no se usan centroides ni desplazamientos artificiales.
`schedule.enabled`, `geocode.jitter_missing` y `licencias.enabled` son false.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_mula -v`: seis tests pasan. Comprueban agrupación,
identidad estable, separación del Plan Especial, fechas documentales distintas,
exclusión de formularios, duplicados, cambios de formato, paginación, conservación
de la salida anterior ante fallo y configuración del manifest.

Extracción real mediante `load_manifest('mula')`, `load_portal_adapter(manifest)` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **8 registros, 53 enlaces**.
La anotación común de entidades informa ocho categorías desconocidas; no se
alteran políticas compartidas ni se presenta el resultado como listo para mapa.

Evidencia local, fuera de los cuatro archivos fuente entregables:

- `evidence/proyectos.jsonl`: registros reales obtenidos por el adaptador.
- `evidence/validation.json`: `live_records`, URLs, limitaciones, runtime y resultado.
- `evidence/captures/inventory-0.html` a `inventory-5.html`: respuestas exactas
  usadas por la extracción final, en el orden de `SOURCES` del adaptador.
- Otras capturas HTML en `evidence/`: páginas inspeccionadas durante el descubrimiento.

No se usaron credenciales, bases de datos, despliegues ni publicación externa.
