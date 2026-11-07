# Bueu — Pontevedra — INE 36004

Verificación: 2026-11-07. Adaptador único `BueuAyuntamientoAdapter`.

## Descubrimiento y alcance

La página oficial de [Urbanismo](https://concellodebueu.gal/urbanismo/)
enlaza el [inventario documental del PXOM](https://concellodebueu.gal/pxom/).
Ambas páginas responden HTTP 200 y sus capturas están en `evidence/`.
El inventario muestra el encabezado «PXOM Bueu (Aprobación definitiva orde
22/09/2017)» y tres grupos documentales: MEMORIA (5), PLANOS (1), PLANOS
ORDENACIÓN (7). Se recorren todos los widgets y todos sus enlaces, sin límite
de registros ni corte del listado. Los 13 documentos forman **un instrumento**,
no 13 proyectos. Se conservan sus títulos originales, grupos, URLs completas y
la página municipal de procedencia. Los enlaces repetidos se deduplican por URL.

La cobertura es deliberadamente parcial: solo este inventario del PXOM. Urbanismo
también enlaza PMUS, inventarios de caminos, trámites y noticias. No se afirma
haber extraído esos otros conjuntos ni todos los instrumentos vigentes de Bueu.
Los formularios de solicitud o comunicación de obras no acreditan concesiones.
No se convierten noticias, anuncios de contratación ni formularios en proyectos.
Licencias deshabilitadas: ambos métodos de licencias producen cero registros.

## Fechas y semántica

`fecha_aprob: 2017-09-22` procede exclusivamente del encabezado municipal,
con cita textual y URL guardadas en `provenance`. No se infiere una fecha de
acuerdo municipal a partir de esa orden. `fecha_publicacion`, `fecha_acuerdo`
y la fecha genérica quedan nulas. La carpeta `/2018/02/` de los PDFs no se
interpreta como fecha de publicación, aprobación o ejecución.
La fase es aprobación definitiva según el encabezado, no licencia concedida.
No se atribuyen parcelas, promotores, importes ni estados de ejecución.

## Integridad y actualización

Es una página estática sin paginación observada. Se rechazan controles de
paginación/continuación reconocidos, cambios del encabezado, redirecciones,
fechas inválidas, documentos sin título o ajenos al dominio municipal y la
pérdida de los mínimos documentales revisados por grupo. Las incorporaciones
se incluyen sin límite superior; una retirada de documentos exige revisión.
Los errores HTTP, de parseo y de tamaño abortan antes de reemplazar el JSONL.
`update_proyectos` vuelve a leer el inventario completo; no usa fechas de
publicación inexistentes para simular un incremental. No se descarga ni analiza
el contenido íntegro de los PDFs, algunos de gran tamaño.

## Geometría

`geometry_status: unavailable`. Existen planos PDF de información, ordenación
y gestión, pero no se ha verificado una geometría vectorial vinculada al
instrumento en esta fuente. No se vectorizan planos ni se inventan coordenadas.
`geometry`, `lat`, `lon` son nulos y `publication_ready` es falso.
`geocode.jitter_missing: false`; `schedule.enabled: false`.

## Validación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_bueu -v` — 4 pruebas correctas.
Cubren agrupación/deduplicación, inclusión de nuevos documentos, procedencia,
separación de fechas, ausencia de geometría, rechazo de paginación y fuentes
incompletas o incorrectas, manifest y licencias deshabilitadas.

Extracción real mediante `load_manifest('bueu')`, `load_portal_adapter(manifest)`
y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro real con
13 documentos**. El registro pasa por la anotación compartida de política de
entidades, que lo clasifica como `unknown` (ratio 1.0, estado `ok`); esto no
acredita geometría ni preparación para publicación.

Evidencias locales no destinadas a commit: `urbanismo.html`, `pxom.html`,
`pxom-live.html`, `proyectos.jsonl`, `validation.json` y
`document-headers.json` (comprobaciones HTTP HEAD de los enlaces PDF).
`validation.json` registra recuento real, fecha de consulta, fuentes y límites.
