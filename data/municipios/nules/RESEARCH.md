# Nules — INE 12082, Castellón

Investigación y extracción real: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y alcance

La web del [Ajuntament de Nules](https://nules.org/) enlaza su portal de
transparencia en `nules.sedelectronica.es`. Se consultó el
[inventario de transparencia](https://nules.sedelectronica.es/transparency/) y su
[sección 7 de urbanismo, obras y medio ambiente](https://nules.sedelectronica.es/transparency/bf0fb568-5cb9-44b9-9842-d643c2626ea3/).
La sección 7 muestra 1.126 documentos, distribuidos en categorías. Se localizaron:

- [7.1 Planeamiento](https://nules.sedelectronica.es/transparency/0882e1fd-ecb8-46f2-9b1e-3ed0fd4cbc2a/):
  320 documentos; PGOU, PERI de Mascarell, modificaciones, planes parciales,
  estudios de detalle, delimitación UE-CARME 1 y modificación 1/2026.
- [7.4 Obras públicas e infraestructuras](https://nules.sedelectronica.es/transparency/78972904-42ef-4ad2-88f7-9508369feada/):
  cuatro documentos y tres proyectos. **Única sección extraída por este adaptador.**
- [7.6 Programas de actuación](https://nules.sedelectronica.es/transparency/582e228f-2c7b-439b-acae-c7628239e020/):
  422 documentos anunciados; reparcelaciones, urbanización y PAI. No se extrae.
- El inventario también anuncia modelos de instancias (7.3) y licencias (7.9,
  254 documentos). No se inspeccionaron sus actos ni se acreditaron concesiones;
  las licencias están desactivadas. El catálogo de trámites no es un registro
  de licencias concedidas. No se utilizan noticias ni anuncios de contratación.

Estos recuentos describen documentos anunciados, no proyectos, concesiones ni
actuaciones ejecutadas. El listado padre tiene «Veure'n més»: se usa únicamente
para localizar 7.4 y su recuento recursivo. No se afirma cobertura de las demás
categorías ni se oculta su paginación.

## Proyectos extraídos y agrupación

1. [Construcción de 76 nichos, módulo XII (A) del cementerio de Nules](https://nules.sedelectronica.es/transparency/e29b1f67-56cd-495b-8965-520ee880a753/).
   Un [proyecto técnico](https://nules.sedelectronica.es/preview-document/f9421be0-412c-42e2-9fce-7a720be32266).
2. [Remodelación de aceras y supresión de barreras de la calle Santa Natalia,
   entre La Llosa y Ramón y Cajal](https://nules.sedelectronica.es/transparency/d937eb2b-d6d8-4e34-8dc3-7cf3bbc70b4f/).
   Un solo registro que agrupa el
   [decreto 2016-1526, titulado aprobación del proyecto](https://nules.sedelectronica.es/preview-document/c0fc7f26-c071-4abf-91f9-c0e6c288abb8)
   y el [proyecto técnico](https://nules.sedelectronica.es/preview-document/a0e0fc5b-312a-410a-855f-4b432fb7d360).
3. [Proyecto de ejecución de remodelación de la Cámara Agraria de Nules](https://nules.sedelectronica.es/preview-document/6c2e8363-627e-4855-97ed-ca59175a020d).
   Documento directamente en 7.4, titulado «01 Projecte B-E Cámara Agraria
   2017-03». La descripción del enlace identifica la obra de remodelación.

Se preservan títulos originales, descripciones de enlaces y URLs estables de
vista previa en `documentos`. Los IDs derivan de la carpeta del proyecto o de la
vista previa del documento directo; no de su posición ni del texto traducido.
Las URLs temporales Wicket se resuelven en sesión anónima a carpetas estables,
sin credenciales, y no se guardan como enlaces documentales.

El adaptador consulta en vivo la categoría padre, abre 7.4 y cada carpeta de
proyecto. Comprueba los recuentos por carpeta y los cuatro documentos únicos
frente al total del padre. Si aparece paginación dentro de 7.4 o de sus proyectos,
una estructura anidada nueva, enlaces inesperados o discrepancias de recuento,
falla antes de escribir la salida. No devuelve una selección truncada. La lista
de proyectos y sus documentos no está precargada en el código.

## Semántica y límites

Cobertura parcial del municipio y completa de la sección 7.4 observada. No se
afirma que este pequeño inventario incluya todas las obras municipales ni que
sea reciente o exhaustivo históricamente. Su presencia no acredita ejecución,
vigencia o estado actual de las obras.

No se emiten fechas de aprobación, acuerdo o publicación: el título de un decreto,
un año en un nombre de documento y la «Data de creació» de su vista previa no
establecen esas fechas. No se extrae el cuerpo de los PDFs ni se deduce una fase
a partir del tipo documental. Sin coordenadas ni geometría verificadas;
`publication_ready: false` y `geometry_status: unavailable` en todos los registros.
El manifest desactiva programación, jitter geográfico y licencias.

## Validación y evidencia local

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_nules -v`
ejecutó **7 pruebas correctas**: agrupación y aislamiento de documentos, IDs,
ausencia de fechas/geometría inventadas, conteos incompletos, paginación,
fuentes inválidas, rechazo de formularios genéricos, manifest y licencias.

Se cargó el manifest mediante `load_manifest('nules')`, se resolvió el adaptador
con `load_portal_adapter` y se ejecutó `backfill_proyectos` directamente, sin
pipeline de publicación ni base de datos. Resultado: **3 registros / 4 documentos**.
La política compartida los clasifica `unknown` por carecer de referencia de
expediente explícita; no se inventa una referencia para cambiar esa clasificación.

En las cuatro vistas previas se comprobó HTTP 200 y un PDF HTTP 200 con
`application/pdf` y firma `%PDF-`. Sólo se capturaron los primeros 1.024 bytes de
cada PDF. La descarga requiere conservar la sesión anónima que abrió la vista
previa y su Referer; una petición inicial sin esa sesión devolvió 403, resuelto
manteniendo la misma sesión. No se usan los tokens temporales del PDF como ID.

Evidencia local, fuera de los cuatro archivos fuente:
`evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML de descubrimiento,
`evidence/live-captures/`, las cuatro vistas previas y sus cabeceras PDF binarias.
`validation.json` incluye recuento real, URLs consultadas, comprobaciones
documentales y limitaciones. No se ejecutaron geocodificación, publicación,
sincronización ni acciones remotas de escritura.
