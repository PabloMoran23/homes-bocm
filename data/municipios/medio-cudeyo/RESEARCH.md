# Medio Cudeyo — INE 39042 — Cantabria

Verificado el 8 de noviembre de 2026. Un adaptador, cobertura parcial de
planeamiento urbanístico oficial. No extrae formularios, noticias, contratación
ni licencias concedidas.

## Descubrimiento y fuentes

- [Urbanismo municipal](https://mediocudeyo.es/web/servicios-municipales/urbanismo/):
  sección «Plan General de Urbanismo», seis ZIP y publicación de aprobación del
  PGOU. Constituyen un instrumento, no siete proyectos. El informe de evaluación
  de edificios que figura después es otra materia y queda excluido.
- [Transparencia: normativa urbanística](https://transparencia.mediocudeyo.es/normativa/normativa-sobre-urbanismo-y-medio-ambiente/):
  «Plan urbanístico municipal» enlaza al archivo oficial AUCAN. Su fecha de
  7 de marzo de 2023 es la de la ficha municipal, no la aprobación del plan.
- [Inventario AUCAN de Medio Cudeyo](https://aplicacionesweb.cantabria.es/aucan/public/zona/costacentral/mediocudeyo):
  aplicación del Gobierno de Cantabria. El HTML solicita
  [el árbol completo del municipio 42](https://aplicacionesweb.cantabria.es/aucan/public/planes?idMunicipio=42).
  El adaptador comprueba el enlace municipal, el nombre y la llamada con ID 42
  antes de leer la respuesta JSON. Este ID local corresponde a Medio Cudeyo;
  el INE completo es 39042, provincia de Cantabria.
- Las secciones de transparencia de
  [planes](https://transparencia.mediocudeyo.es/economica/planes-urbanisticos-y-estudios-de-impacto-ambiental/)
  y [obras públicas](https://transparencia.mediocudeyo.es/economica/obras-publicas/)
  no mostraron registros en los HTML revisados. No se deduce que no existan obras.

## Extracción y semántica

Resultado vivo: **16 instrumentos y 90 enlaces documentales** de la rama
«Actual»: PGOU, doce modificaciones (números 1–11 y modificación del Sector 30),
dos planes parciales (Sector 14.2 en Heras y Sector 26 en Solares) y Catálogo de
Edificaciones en Suelo Rústico. Se excluye explícitamente «No Vigente».

Los documentos del PGOU (60) incluyen informes, planos, subsanaciones y los
avisos de anulación del Sector 22. Se conservan títulos y rutas completas:
«Actual» es la clasificación del archivo, no una certificación jurídica propia
de vigencia íntegra. Una carpeta indica una subsanación pendiente de entrega de
plano y publicación. Los avisos de anulación y pendientes quedan además en
`advertencias_fuente`. Las doce modificaciones tienen registro propio enlazado
al PGOU; sus documentos no se duplican en el padre. No se fabrican números de
expediente: los IDs internos son hashes del nombre del instrumento y su padre.

`fecha_acuerdo` procede del encabezado «CROTU/Ayto.» y `fecha_publicacion` del
«BOC». `fecha_aprob` solo se rellena si existe una sección explícita «Aprobación
definitiva»; en las modificaciones se conserva únicamente el acuerdo, sin
inferir fase. `fecha` queda nula. No se usan fechas de subida de los archivos ni
la firma del anuncio como fecha del acuerdo.

Se descargaron y capturaron, como contraste documental, la publicación municipal
del PGOU (CVE-2011-1810), y los documentos AUCAN 29427, 31387, 28984 y 28862.
La primera página del PGOU confirma acuerdo de 16/11/2010 y publicación de
18/02/2011. El PDF 31387 (CVE-2022-6505) confirma aprobación del Sector 26 el
04/08/2022 y publicación el 01/09/2022; su firma de 18/08/2022 no sustituye esas
fechas. Se conservan enlaces al resto de documentos sin descargar todos los
binarios voluminosos ni interpretar su contenido íntegro.

## Cobertura y geometría

No se ha verificado un inventario de licencias concedidas. Ambos métodos de
licencias devuelven vacío y estado disabled. Actualización de proyectos = nueva
instantánea completa; no promete histórico ni bajas incrementales.

La respuesta actual es un único árbol JSON sin paginación; se recorre completo,
sin límites de registros ni documentos. Un envoltorio paginado, metadatos de
continuación o nodos/categorías desconocidos producen error, no un éxito parcial.

`geometry_status: unavailable`. Urbanismo enlaza un «Mapa virtual PG» en
http://www.munisig.com/munisig/v3.1/index.html?municipio=MedioCudeyo;
no se ha verificado una capa vectorial asociable a cada instrumento. Los planos
PDF no se convierten en geometría. Coordenadas y geometría nulas, sin jitter.

El guard compartido de entidades clasifica los 16 registros como pendientes por
no disponer de referencia de expediente reconocida y emite `adapter_incident`
(`unknown_entity_spike`). Se conserva esa anotación sin inventar referencias ni
alterar la política compartida. Son instrumentos reales documentados, pero no
están listos para publicación (`publication_ready: false`).

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_medio_cudeyo -v
```

Cuatro pruebas: fechas y jerarquía, deduplicación de documentos, exclusión de
histórico, avisos de anulación, IDs estables, 75 documentos sin truncado,
rechazo de cambio de esquema/paginación y licencias deshabilitadas sin red.
Extracción viva mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Configuración opcional
`capture_dir: evidence` conserva las tres respuestas usadas por el adaptador.

Evidencias locales (no para commit): `evidence/proyectos.jsonl`,
`evidence/validation.json`, HTML, inventario JSON y muestras PDF/texto.
Manifest con `schedule.enabled: false`, `licencias.enabled: false` y
`geocode.jitter_missing: false`. No se han ejecutado publicación ni despliegue.
