# Urnieta — INE 20072, Gipuzkoa

Revisión y extracción directa: 2026-11-09. Un único adaptador municipal.

## Descubrimiento y alcance

Desde https://www.urnieta.eus/es/ se accede por Ayuntamiento → Acuerdos y
normativas → «Planes de desarrollo de la organización territorial» a:

https://www.urnieta.eus/es/hiri-antolamendurako-garapen-planak

Este inventario oficial, accesible sin sesión, publica documentos técnicos de
instrumentos urbanísticos, no formularios de solicitud ni anuncios de contratación.
La extracción toma todos los bloques `.documentos .documento` dentro de
`#main-content`. La captura tiene ocho instrumentos y ocho enlaces PDF/ZIP:

| Instrumento | Fecha literal del catálogo | Documento |
| --- | --- | --- |
| Texto refundido del proyecto de reparcelación AIU 32 Babilonia | 18·09·2026 | PDF, HTTP 404 |
| Aprobación inicial del proyecto de urbanización AIU 32 Babilonia | 06·05·2026 | ZIP, disponible |
| Modificación puntual del Plan Parcial AIU 32 Babilonia | 16·02·2026 | PDF, disponible |
| Segunda aprobación inicial del Plan Parcial AIU 28 Miravalles | 13·10·2026 | ZIP, disponible |
| Plan Parcial AIU 31 Azkarate | 01·10·2025 | ZIP, disponible |
| Estudio de Detalle AIU 32 Babilonia | 02·02·2026 | ZIP, disponible |
| PAU AIU 32 Babilonia | 27·01·2025 | ZIP, disponible |
| Plan Parcial AIU 32 Babilonia, texto refundido 2020 | 05·07·2021 | PDF, disponible |

La ausencia del PDF de reparcelación no borra el instrumento realmente publicado
en el inventario: se conserva su URL con `availability: unavailable` y
`http_status: 404`. Los demás documentos se verificaron con GET y firma PDF/ZIP,
leyendo solo el comienzo de cada archivo (algunos ZIP superan 160 MB). No se afirma
haber inspeccionado íntegramente los proyectos o descomprimido los archivos.

El enlace de icono y el de título se deduplican por URL. Los documentos de un mismo
título normalizado se agrupan en un registro con identidad hash determinista y
proveniencia por documento. Los instrumentos diferentes de un mismo ámbito AIU
no se fusionan: un plan parcial, su modificación, PAU, urbanización, reparcelación
y estudio de detalle son instrumentos distintos. Los cambios de título pueden
cambiar la identidad; no se presenta esto como un registro histórico de expedientes.

No hay controles de paginación en el inventario capturado. Si aparecen enlaces
activos de paginación, el adaptador falla expresamente hasta implementar su
recorrido. Nunca aplica un límite silencioso de registros. Una página vacía,
estructura incompleta o tipo de instrumento desconocido también exige revisión.
La actualización refresca la misma instantánea completa, sin marcar bajas ni
pretender un incremental histórico.

## Fechas, fase y límites

La web etiqueta las fechas únicamente como `fecha`. No acredita si son publicación,
carga, actualización o acuerdo. Se retienen en `documentos[].fecha_catalogo` y
`fecha_fuente`; `fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan
nulas. Solo se asigna fase cuando el título dice expresamente aprobación inicial
(o segunda aprobación inicial). «Texto refundido» no se transforma en aprobación
definitiva. La categoría 2025 de Miravalles no coincide con su fecha 13·10·2026:
se conserva la fecha literal sin corregirla ni usarla como fecha de acuerdo.

Cobertura parcial: exclusivamente el inventario municipal de planes de desarrollo,
no todas las obras físicas, licencias, instrumentos históricos o registro foral.
Se revisaron también:

- https://www.urnieta.eus/es/urbanismo-servicios — departamento y noticias; no se
  confunden noticias generales con instrumentos ni licencias concedidas.
- https://www.urnieta.eus/es/proyectos-y-planes — catálogo heterogéneo con planes
  organizativos; se excluye de esta extracción para mantener un alcance urbanístico.
- https://www.urnieta.eus/es/hapo-pgou2 — PGOU y navegación por sus documentos;
  fuera de este adaptador acotado. No se convierte cada memoria/plano en proyecto.

No se ha verificado un registro de licencias concedidas. Ambos métodos de licencias
escriben salida vacía con estado `disabled`; no generan registros de trámites.

## Geometría

`geometry_status: unavailable`. La página municipal
https://www.urnieta.eus/es/geo-urnieta1 describe y enlaza https://geournieta.org/es
como visor de PGOU, catastro y callejero. Esto no acredita una geometría vectorial
asociada por identificador a los ocho instrumentos extraídos. No se asignan
coordenadas, centroides o CRS ni se vectorizan PDFs. `publication_ready: false`.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_urnieta -v`: seis pruebas de agrupación de
documentos, instrumentos distintos de un mismo ámbito, fechas no inferidas,
rechazo de paginación/estructura/tipos ajenos, disponibilidad documental,
contrato del manifest y conservación de salida ante fallo.

Extracción real invocando `UrnietaAyuntamientoAdapter.backfill_proyectos`:
ocho registros, siete documentos accesibles y uno con HTTP 404. Evidencia local
no destinada a commit en `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/inventory-live.html`, capturas de descubrimiento HTML y
`evidence/document-checks.json`. Los registros conservan todos los enlaces.

Manifest: `schedule.enabled=false`, `geocode.jitter_missing=false`,
`licencias.enabled=false`. Sin cambios compartidos, dependencias o publicación.
