# Pravia — INE 33051, Asturias

Verificado el 2026-11-08 con el runtime preinstalado. Se inspeccionaron primero
`municipio/manifest.py`, `municipio/adapters/portal.py`, el registro de adaptadores y
los ejemplos de Hernani y Manlleu. No hay cambios en fuentes compartidas.

## Fuente y cobertura

Inventario oficial actual:
https://www.ayto-pravia.es/urbanismo-y-vivienda

La página contiene tres instrumentos documentados, no tres obras nuevas:

- Plan General de Ordenación del Concejo de Pravia — Texto Refundido: 136 enlaces.
- Catálogo Urbanístico de Pravia: 9 enlaces.
- Plan Especial de Protección del Casco Antiguo de Pravia: 4 enlaces, incluidos
  tomos 1–2, tomos 3–6, edicto y publicación BOPA.

El PGO y el Catálogo son secciones distintas del índice municipal; los planos,
memorias, tomos y anuncios se agrupan en su instrumento y no generan registros
adicionales. Cada enlace conserva título, URL original y página de procedencia.
Los identificadores locales corresponden al instrumento/sección y no se presentan
como números oficiales de expediente. No se asigna un expediente regional al
Catálogo a partir del expediente del PGO.

Se recorren los dos subinventarios descubiertos en la sección del PGO:

- https://www.ayto-pravia.es/web/ayto-pravia/urbano-pravia-e-1000
- https://www.ayto-pravia.es/web/ayto-pravia/urbano-pravia-e-2500

Se deduplican URLs y se evita repetir páginas cíclicas. No existe paginación en las
páginas examinadas. La aparición de controles de paginación o enlace siguiente
provoca error explícito; no se limita el número de filas ni documentos. Se falla
ante secciones desconocidas, inventarios vacíos, pérdida de instrumentos o rutas
documentales no revisadas. La pérdida aislada de un enlace de documento entre dos
versiones no se detecta comparando históricos; no existe estado persistente.

Cobertura parcial: inventario publicado de estos instrumentos, sin enumeración
exhaustiva de modificaciones posteriores, expedientes en tramitación o todas las
obras físicas municipales. No se afirma vigencia jurídica ni aprobación basándose
solo en la presencia en la página. No es un registro de actividad reciente.

## Fechas, exclusiones y calidad

El índice no identifica fechas de publicación, acuerdo o aprobación de cada
instrumento. `fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan
nulos; no se deducen fechas del nombre del PDF, parámetros `t`, copyright o fecha
de consulta. Tampoco se asigna fase por el tipo de instrumento.

https://www.ayto-pravia.es/declaraciones-responsables contiene normativa y modelos
para presentar declaraciones, no licencias concedidas. Se excluye íntegramente de
la extracción de licencias. Se excluye asimismo el formulario tributario de
Plusvalía del índice de urbanismo. No se usan anuncios de contratación como obras
ni noticias genéricas como proyectos.

https://www.ayto-pravia.es/documentos-sometidos-a-informacion-publica remite al
tablón y noticias; no ofrece allí un inventario de expedientes estructurado. No se
ha incorporado ese histórico en este adaptador.

Anomalías conservadas en `enlaces_incompletos` y evidencias:

- Plano 37 — Villamuñiz / Villafría / Ocea / La Pandiella: href vacío.
- Plano Urbano — Pravia — 05A (E-2500): href vacío.
- Plano 05C (E-2500): enlace original con `groupId=184238_id@`, conservado sin
  corregirlo artificialmente. Su disponibilidad no se da por verificada.

Se verificaron HTTP 200/application/pdf en los cuatro documentos del Plan Especial,
con capturas PDF locales; no se descargaron ni comprobaron todos los 149 enlaces.
La procedencia documental es el índice municipal, no una lectura integral de PDFs.
La clasificación compartida `entity_policy` devuelve `pendiente` para los tres
registros por falta de referencia oficial estructurada; no se alteró su regla ni
se inventaron expedientes para superar ese resultado. Requieren revisión antes de
cualquier publicación; `publication_ready=false`.

## Geometría

`geometry_status: unavailable`. Sin geometría vectorial vinculada verificada;
`geometry`, `lat` y `lon` nulos. Los planos PDF no se convierten en puntos.
La página de declaraciones enlaza el visor regional:
http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/VisorRPGUR.php?id_instrumento=3096
No se ha verificado una capa descargable ni su correspondencia individual con los
tres instrumentos. No se infieren coordenadas del centro municipal.

## Validación reproducible

Desde la raíz, con el Python solicitado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_pravia -v
```

Cuatro pruebas offline: agrupación y procedencia, fechas nulas y exclusiones,
rechazo de cambios/paginación, subinventarios con deduplicación/ciclos/enlaces
vacíos, licencias deshabilitadas y carga del manifest. La extracción real se
realizó mediante `load_portal_adapter(load_manifest('pravia'))` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`portal.config.capture_dir='evidence/captures'` solo en memoria.

Resultado: **3 registros reales**, **149 enlaces documentales**, dos enlaces
vacíos y dos subpáginas recorridas. `evidence/validation.json` contiene recuentos,
URLs consultadas, fecha de verificación y limitaciones. Las capturas HTML del
adaptador quedan en `evidence/captures/`; las consultas auxiliares y muestras PDF
en `evidence/`. Evidencia local fuera de las cuatro fuentes a entregar.

Manifest: municipio/provincia exactos, `schedule.enabled=false`,
`geocode.jitter_missing=false` y `licencias.enabled=false`. Actualización como
instantánea completa del inventario; sin despliegue, publicación ni base de datos.
