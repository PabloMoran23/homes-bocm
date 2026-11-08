# A Guarda — INE 36023, Pontevedra, Galicia

Verificado el 2026-11-07 mediante peticiones HTTP reales. Adaptador:
`municipio.adapters.a_guarda:AGuardaAyuntamientoAdapter`.

## Descubrimiento y fuentes oficiales actuales

La página municipal de [Urbanismo](https://www.aguarda.es/servizos-municipais/urbanismo/)
enlaza en su navegación los inventarios de
[Ordenanzas](https://www.aguarda.es/servizos-municipais/urbanismo/ordenanzas/) y
[Planos](https://www.aguarda.es/servizos-municipais/urbanismo/planos/).
El adaptador descubre estos enlaces cada vez; no usa una noticia como semilla.
Ambos inventarios son páginas estáticas completas, sin paginación activa.
Si aparece paginación, el adaptador falla explícitamente antes de escribir resultados.
Los años de documentos históricos no son fechas de actualización del inventario.

Ordenanzas identifica expresamente dos instrumentos con PDF:

- [Plan xeral de ordenación urbana (1993)](https://www.aguarda.es/wp-content/uploads/2013/11/ordenanza_pxou_1993.pdf).
- [Modificación Nº1 do P.X.O.U. (1997)](https://www.aguarda.es/wp-content/uploads/2013/11/ordenanza_pxou_1997.pdf).

Urbanismo declara que el PXOU está vigente y su aprobación definitiva es del
**29.07.93**. Se extrae como `fecha_aprob: 1993-07-29`, con URL de procedencia;
no se interpreta como fecha de publicación. El año 1997 identifica la modificación,
pero no permite inventar día/mes ni asegurar una fase concreta. La modificación
no lleva fecha de aprobación ni fase inferidas. Tampoco se usan como fechas las
rutas de subida de los documentos (2013/11, 2014/04).

Planos ofrece un índice de referencia en alta resolución y 34 láminas numeradas
(2.1–2.5, 3.1–3.5, 4.1–4.7, 5.1–5.17). Se inspeccionó visualmente la lámina
2.1: su cartela identifica expresamente el Plan Xeral de Ordenación Urbana del
Concello de A Guarda. El índice y las láminas se agrupan con el PXOU; no son
35 proyectos distintos. La miniatura alternativa del índice se omite a favor
del enlace explícito de alta resolución. Los documentos conservan sus URLs y
la página de inventario que los publica. El enlace al antiguo visor Xunta
`http://www.planeamentourbanistico.xunta.es/` se conserva aquí como pista de
investigación, no como documento ni como geometría verificada.

## Cobertura y exclusiones

Resultado real: **2 registros**, PXOU con **36 documentos** (normativa, índice y
34 láminas), modificación nº1 con **1 documento**. Ambos PDF se descargaron y
validaron por su cabecera PDF durante la extracción. Las láminas conservan enlaces;
no se descargan todas en cada actualización. Las capturas de investigación incluyen
el índice y la lámina 2.1. Las copias PDF son escaneadas; `pdftotext` no produjo
texto útil y no se atribuyen acuerdos ni fechas desde OCR no verificado.

Cobertura parcial del inventario documental municipal publicado hoy: no es un
histórico exhaustivo de modificaciones, un registro de obras en ejecución ni una
certificación jurídica consolidada del planeamiento. No se afirman expedientes
actuales de licencia o proyectos nuevos por el hecho de ser documentos accesibles.

La página de [Vías e Obras](https://www.aguarda.es/servizos-municipais/vias-e-obras/)
se revisó: combina presentación del servicio y seis noticias recientes. No se usa
ese bloque limitado como si fuera un inventario completo. La página de
[Procedementos](https://www.aguarda.es/servizos-municipais/urbanismo/procedementos/)
contiene solicitudes/comunicaciones: no acredita licencias concedidas. No se
convierten formularios, presupuestos, anuncios de contratación o noticias generales
en registros de proyectos. `licencias.enabled: false`; sus métodos escriben vacío.

`geometry_status: unavailable`: cartografía JPG escaneada, sin geometría vectorial
vinculada y verificada. No se derivan coordenadas, CRS o polígonos desde las imágenes.
`publication_ready: false`, `geocode.jitter_missing: false`, `schedule.enabled: false`.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_a_guarda -v`: **4 pruebas pasan** (agrupación y
estabilidad de identidad, semántica de fechas, exclusión de formularios, fallos por
cambios/paginación/enlaces externos, licencias sin red, carga del manifiesto).
Se ejecutó `AGuardaAyuntamientoAdapter.backfill_proyectos` con `config.evidence_dir`
apuntando a `evidence/`: **2 registros reales**, sin datos sintéticos.

Evidencia local, no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, HTML de Urbanismo/Ordenanzas/Planos/Vías e Obras,
ambos PDF y las dos imágenes revisadas. La validación incluye hora UTC, fuentes,
número de documentos por instrumento y limitaciones. `update_proyectos` repite el
inventario completo y sustituye el resultado sólo tras validar los documentos;
no promete un histórico incremental ni interpreta bajas documentales como derogación.
No se ha usado publicación, base de datos ni despliegue.
