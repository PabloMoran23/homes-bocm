# Santa Comba — INE 15077, A Coruña

Verificación en vivo: 2026-11-07. Un único adaptador, sin licencias ni ejecución
programada, sin coordenadas inventadas. `geocode.jitter_missing: false`.

## Descubrimiento y fuentes oficiales

- https://www.santacomba.es/ enlaza expresamente «PLAN ÚNICO DE CONCELLOS
  (POS+)» a https://plan-unico.dacoruna.gal/santa-comba/.
- Este inventario de la **Deputación Provincial da Coruña** devuelve HTTP 200,
  identifica Santa Comba y publica 69 «Obras aprobadas». Es una fuente provincial
  oficial enlazada por el ayuntamiento; no se presenta como autoría municipal.
- La sede, en
  https://sede.santacomba.es/sxc/es/portal_transparencia/Institucional_Organizativa/Planes_y_Programas/Planes_Programas.html,
  enlaza «Planes y Proyectos» al inventario urbanístico de la Xunta
  (`http://www.planeamentourbanistico.xunta.es/siotuga/inventario?inv=1&idconcello=15077`).
  Ese inventario externo no se extrae ni se afirma haber verificado su contenido.
- https://www.santacomba.es/s4-guia-municipal/c19-plan-xeral-de-ordenacion-municipal/pxom.html
  publica artículos del PXOM. No contiene el inventario de expedientes utilizado.
  No se convierten los artículos, las figuras genéricas mencionadas en ellos ni
  los formularios de la sede en proyectos o licencias concedidas.

## Extracción y semántica

La tabla HTML «Lista de obras e investimentos» contiene todos los ejercicios
2017–2026. Se recorren sus **69 filas** y se extraen **68 obras físicas**. Se excluye
«Subministración pequeno equipamento Brigada municipal de Obras e Servizo
municipal de Limpeza» (2025), por ser suministro. Ejemplos reales: pavimentación
y pluviales en Montouto, reforma para Centro de Día y reposición de aceras en
la rúa Pontevedra. Se conservan título original, ejercicio, presupuesto y
aportación, con importes decimales exactos expresados como cadenas en euros.

No hay paginación en la versión revisada: el selector está en «Todos», la tabla
incluye los diez ejercicios y su tamaño coincide con el contador publicado.
Las tarjetas duplican la tabla y no se extraen. Si cambia el esquema, aparece
paginación, se filtra el ejercicio, falta el contador o no coincide con la tabla,
el adaptador falla explícitamente antes de reemplazar los resultados anteriores.
No existe límite artificial de filas. Nuevas categorías desconocidas requieren
revisión; no se aceptan automáticamente como obras.

Una fila es una actuación agregada según el inventario: no se desdoblan sus
caminos o parroquias en proyectos inventados. No hay referencias de expediente ni
enlaces a documentos técnicos en las filas actuales. `documentos` queda vacío;
si la celda del objeto incorpora enlaces, se conservan agrupados en la misma
actuación. Las fotografías generales de la página no se asignan por semejanza.
Los IDs derivan del ejercicio y título normalizado; una corrección del título
puede cambiar el ID. Las actualizaciones releen toda la instantánea, sin fingir
incrementalidad ni escribir un cursor no sustentado por la fuente.

«Obras aprobadas» se conserva como `estado_segun_fuente`: no demuestra ejecución,
terminación, adjudicación ni concesión de licencia. El ejercicio presupuestario
no es fecha de publicación, acuerdo o aprobación: esos campos se omiten. No se
extrae ninguna licencia. Cobertura parcial: solo inversiones POS+ publicadas, no
todo el planeamiento, obras, contratos ni licencias de Santa Comba.

## Geometría y clasificación compartida

`geometry_status: unavailable`, `publication_ready: false`. No se ha verificado
geometría vinculada a las actuaciones; no se geocodifica ni se fabrican centroides.
La política compartida del registro deja las 68 filas como `pendiente`, con
`insufficient_identity_evidence` y reporte `adapter_incident / unknown_entity_spike`,
porque este inventario no facilita referencias oficiales de expediente. Este es
un límite para su uso posterior, conservado en la validación; no se inventan
referencias para sortearlo ni se modifica la política común. El extractor directo
sí recupera obras reales, contrastables por ejercicio y título en la fuente.

## Validación reproducible y evidencias locales

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_santa_comba -v`: **7 pasan**.
Cubren exclusión de suministros/formularios/anuncios, importes, semántica de
fechas, documentos agrupados, IDs estables, paginación y tablas incompletas,
actualización y conservación del resultado ante errores, y manifest.

Extracción real mediante `load_manifest('santa-comba')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`:
**68 registros únicos**; 69 filas de origen, 1 suministro excluido.
Para capturar HTML se estableció `manifest.portal.config['evidence_dir']` con la
ruta local de `evidence` antes de cargar el adaptador.

`evidence/proyectos.jsonl` contiene los registros reales; `evidence/validation.json`
incluye contador, URLs, limitaciones, exclusión y reporte de la política compartida.
`evidence/pos-live.html` captura la respuesta de la extracción, `pos-inventory.html`
la exploración inicial y `discovery-0.html` a `discovery-2.html` las tres páginas de
descubrimiento. Evidencias locales, no destinadas a commit. Sin publicación,
servicios de producción ni cambios de dependencias o fuentes compartidas.
