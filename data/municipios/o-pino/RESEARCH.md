# O Pino — INE 15066, A Coruña

Comprobación en vivo: 2026-11-09. Adaptador de obras públicas reales, limitado al
inventario provincial POS+ del municipio. No constituye un registro completo de
urbanismo, proyectos ni licencias municipales.

## Descubrimiento y fuentes

- Portal oficial municipal: https://opino.gal/ (HTTP 200). Su menú enlaza Urbanismo:
  https://opino.gal/c/urbanismo/ (HTTP 200). Es un archivo paginado de noticias y
  formularios, no un inventario de licencias concedidas. La primera página mezcla
  noticias de rehabilitación de un colegio con modelos de comunicación previa,
  ocupación de vía pública y cambio de titularidad. No se extrae ninguna página de
  este archivo como proyecto/licencia; tampoco se pretende cubrir su histórico.
- Sede oficial descubierta: https://opino.sedelectronica.gal/info.0. Su catálogo de
  trámites no acredita concesiones; no se utiliza como registro de licencias.
- Fuente efectiva: https://plan-unico.dacoruna.gal/o-pino/ (HTTP 200), inventario
  «PLAN ÚNICO O Pino» de la Deputación Provincial da Coruña, con «Obras aprobadas».
  Incluye tabla «Lista de obras e investimentos», selector de todos los ejercicios
  y datos completos serializados en el componente Astro CmpObrasEjercicio.
  Identidad comprobada en estos datos: nombreOficial=O Pino, DIR3=L01150660,
  correspondiente al municipio INE 15066, provincia A Coruña.

El manifiesto usa `proyectos.source: ayuntamiento` como ruta del adaptador de portal
admitida por el esquema compartido. La fuente efectiva es **la Deputación**, como
indican sus notas y los campos `source: diputacion`, `organismo_fuente`, `origen`,
`inventory_url` y `documentos` de cada registro. No se atribuyen los datos a la web
municipal ni se usa una noticia o licitación como sustituto de un proyecto.

## Cobertura y significado

La ejecución real obtiene **60 obras**: 2017=6, 2018=10, 2019=10, 2020=3,
2021=5, 2022=6, 2023=2, 2024=7, 2025=7 y 2026=4. Ejemplos:
«Sinalización de Pedrouzo e viarios principais do Concello do Pino»,
«Viario de Quintans a Carolliño e outros», «Reforzo de firme de Pumar a Vilarmeao».
Son actuaciones físicas del inventario de obras aprobadas, no gastos sociales,
corrientes, reducción de deuda ni totales financieros.

Se conserva ejercicio presupuestario, denominación, presupuesto y aportación
provincial en euros, como decimales textuales para evitar pérdida de precisión.
`estado_fuente: Obras aprobadas` reproduce la clasificación del inventario, sin
inferir ejecución, adjudicación, terminación ni fecha de aprobación. El ejercicio
**no es una fecha**. Se omiten `fecha`, `fecha_publicacion`, `fecha_acuerdo` y
`fecha_aprob`: la página no proporciona estas fechas para cada obra.

La tabla y los datos completos deben coincidir en cada tupla de ejercicio,
denominación e importes. El selector debe cubrir todos los ejercicios. `todos`
es un bloque de totales financieros sin obras; no es otra página. No hay
paginación de obras en la fuente actual: las 60 filas están en el HTML recibido.
Si aparecen enlaces de paginación, datos incompletos, otra identidad municipal o
un cambio de estructura, el adaptador falla antes de reemplazar el JSONL. No hay
límite artificial de filas ni selección de unos pocos ejercicios.

Una fila se corresponde con una obra; no se dividen los títulos «e outros» en
proyectos inventados. Las vistas duplicadas de tarjetas/tabla no generan registros
adicionales. Duplicados idénticos se agrupan; importes incompatibles para el mismo
ejercicio y título provocan error. Al no existir identificador de expediente, el
ID deriva del ejercicio y título normalizado: una corrección del título cambia el
ID y dos actuaciones homónimas del mismo ejercicio no pueden distinguirse.

La fuente no ofrece enlaces individuales a memorias, planos o acuerdos de cada
obra. `documentos` retiene el enlace al inventario HTML y lo identifica como tal;
no se presenta como PDF ni como expediente completo. No se crean registros por
fotografía o documento. No se cubren obras fuera del POS+, planeamiento, ni
licencias privadas. Las licencias permanecen deshabilitadas y sus métodos escriben
un fichero vacío.

## Geometría

`geometry_status: unavailable`. El inventario utilizado no aporta geometrías ni
coordenadas por obra. No se deducen posiciones a partir de nombres de lugares, ni
se usa el centroide municipal. `geocode.jitter_missing: false` y
`publication_ready: false`; disponer de obras verificadas no acredita geometría
lista para publicación.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_o_pino -v` — **6 pruebas, OK**.
Comprueban semántica/procedencia, importes, omisión de fechas y coordenadas,
agrupación y conflictos, identidad municipal, truncamiento, cobertura de ejercicios,
paginación y resolución del manifiesto con licencias deshabilitadas.

Extracción real mediante `OPinoAyuntamientoAdapter('o-pino',
{'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Resultado: 60 registros. `update_proyectos` vuelve a leer la instantánea completa;
no usa un cursor que pueda omitir ejercicios anteriores ni modifica estado externo.

Evidencia local, excluida de los cuatro archivos fuente entregables:
`evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/pos-live.html`
(captura de la petición real del adaptador), `evidence/pos.html`,
`evidence/home.html` y `evidence/urbanismo.html` (descubrimiento).
El informe recoge hora UTC, recuento, URL efectiva, cobertura y limitaciones.
`schedule.enabled: false`. Sin cambios compartidos ni dependencias nuevas.
