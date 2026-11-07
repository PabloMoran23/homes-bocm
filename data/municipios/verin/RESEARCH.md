# Verín — INE 32085, Ourense, Galicia

Verificación: 2026-11-07. Adaptador: `municipio.adapters.verin:VerinAyuntamientoAdapter`.
Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuente oficial actual

El catálogo municipal https://www.verin.es/planeamento/ devuelve HTTP 200 y
publica ocho tarjetas de instrumentos urbanísticos, distribuidas en planeamiento
xeral (3), protección del patrimonio (2) y desenvolvemento (3). Las tarjetas
conducen al subdominio municipal `urbanismo.verin.gal`. Se parte del catálogo,
no de noticias individuales ni de títulos de licitación. La biblioteca municipal
https://www.verin.es/document-library/ también apareció en la búsqueda, pero sus
ordenanzas y formularios no se confunden con proyectos ni licencias concedidas.

Se extraen estos seis inventarios enlazados por el catálogo:

| Instrumento | Fuente documental | Archivos |
| --- | --- | ---: |
| PXOM Verín, febrero 2023 | https://urbanismo.verin.gal/pxom/pxom.html | 1285 |
| IOP, documento AD R03 | https://urbanismo.verin.gal/iop2020/iop2020.html | 240 |
| PEPRICH, centro histórico y San Lázaro | https://urbanismo.verin.gal/peprich/peprich.html | 1533 |
| PERI APR-45, Os Coutos | https://urbanismo.verin.gal/apr45/apr45.html | 29 |
| Plan especial del complejo balneario asistencial de Caldeliñas | https://urbanismo.verin.gal/caldelinas/caldelinas.html | 29 |
| PEID de Preguiza | https://urbanismo.verin.gal/preguiza/preguiza.html | 42 |

Resultado: **6 registros reales, 3158 enlaces de archivo**. Un registro por
instrumento; memorias, anexos, planos y versiones permanecen en `documentos`,
con nombre, ruta, tamaño, enlace directo y URL del inventario de procedencia.
Se conservan todos los archivos, no solo PDFs; su presencia no significa que cada
archivo sea un documento técnico interpretado. No se descargan los gigabytes del
archivo municipal. Se verificó un PDF por instrumento mediante GET, HTTP 200 y
cabecera `%PDF-`, conservando los primeros 1024 bytes como captura de comprobación.
Los demás enlaces se derivan del inventario oficial, sin verificar su descarga.

## Semántica y cobertura parcial

La presencia en el catálogo disponible hoy **no acredita vigencia jurídica**.
Incluye materiales históricos y fases distintas. La descripción de cada tarjeta
se conserva como `descripcion`; por ejemplo, el municipio presenta la IOP como
publicada en BOP y en vigor desde 18 de mayo de 2021. Se conserva esa afirmación
atribuida a la fuente, sin validar su vigencia actual ni convertirla en un acuerdo.
Las menciones a febrero/abril de 2023, los códigos de carpeta AI/AD, las fechas de
modificación de archivos y la generación Snap2HTML no se convierten en fechas de
publicación o aprobación. No se emiten `fecha`, `fecha_publicacion`, `fecha_acuerdo`
ni `fecha_aprob`, pues no se han contrastado los actos correspondientes.
`vigencia_verificada=false`, `publication_ready=false`.

Dos instrumentos del catálogo quedan fuera y se identifican en el resultado del
adaptador y en `validation.json`:

- https://urbanismo.verin.gal/pxom2012 — visor antiguo con frames; plan de 2012
  etiquetado como histórico por el municipio.
- https://urbanismo.verin.gal/pepri — visor antiguo con mapas de imagen y zonas HTML.

Se inspeccionaron ambos visores (HTTP 200), pero no se implementa su recorrido.
No se afirma cobertura completa del planeamiento, de obras físicas ni del
histórico municipal. No hay registro verificado de licencias concedidas; sus
métodos escriben un JSONL vacío y devuelven `disabled=true`.

## Recorrido y controles

Las seis páginas Snap2HTML contienen íntegro el árbol en arrays `D.p([...])`.
Se decodifican como JSON sin ejecutar JavaScript. Se recorren todas las carpetas,
sin paginación, límites de registros ni filtrado por nombre. Se comprueba el número
de archivos contra `numberOfFiles` y las estadísticas visibles, además del total
de carpetas y la ausencia de enlaces duplicados. Los enlaces se resuelven desde
`sourceRoot`, siguiendo la lógica del visor y escapando caracteres Unicode,
espacios y `#`. No se usan rutas locales Windows como URLs.

Los contadores del catálogo deben coincidir con las tarjetas. Una paginación
activa reconocida provoca error explícito, en vez de truncar el inventario. Un
nuevo visor de formato desconocido también falla; solo los dos visores antiguos
identificados se excluyen expresamente. La actualización vuelve a leer el catálogo
completo. Un error de descarga o formato no reemplaza el JSONL anterior.

## Geometría y validación

`geometry_status: unavailable`. Los inventarios incluyen planos y documentos,
pero no se ha identificado una geometría vectorial enlazable a cada instrumento.
No se digitalizan planos, no se asignan centroides y no se inventan coordenadas.
`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.

Cinco tests con `python -m unittest municipio.test_verin -v`: agrupación y exclusiones,
deduplicación, URLs documentales y caracteres especiales, detección de inventarios
incompletos/paginación, conservación del resultado ante fallo, licencias vacías y
configuración municipal. Extracción real con `backfill_proyectos`, sin orquestación,
publicación ni acceso a bases de datos. Evidencia local en `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas HTML en `evidence/captures/` y muestras PDF.
