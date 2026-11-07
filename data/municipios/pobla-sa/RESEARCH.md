# Pobla, Sa — INE 07044 — Illes Balears

Verificado el 2026-11-07 con el runtime preinstalado. Adaptador único:
`municipio.adapters.pobla_sa:PoblaSaAyuntamientoAdapter`.

## Descubrimiento y fuentes oficiales

El área municipal de [Urbanisme](https://sapobla.cat/ca/serveis-municipals/urbanisme)
expone un inventario de enlaces relacionados: trámites, Normes subsidiàries de sa
Pobla 2003, BOIB acord de les NNSS, visor IDEIB y Pla Territorial Insular de Mallorca.
El scraper descubre los enlaces en las tarjetas `h3` dentro de `main`, no en menús
ni en una lista de expedientes inventada. No hay paginación en esta página.
Si aparece un paginador o enlace siguiente, falla explícitamente; tampoco acepta
inventarios vacíos, múltiples planes base ambiguos o desaparición de documentos.

Fuentes documentales descubiertas y verificadas en vivo:

- [Normes subsidiàries de sa Pobla 2003](https://drive.google.com/file/d/1t5UATF7L-p-ZM_sYnLoEziZ3J4lp4Uxx/view).
  Drive es alojamiento externo enlazado por el Ayuntamiento: HTTP 200 y título
  público `REVISION DE LES NNSS.APROVACIÓN DEFINITIVA 2003.pdf - Google Drive`.
  Se verifica su identidad, pero no se ha descargado ni interpretado ese PDF.
- [BOIB enlazado por Urbanisme](https://sapobla.cat/sites/cilma_sa_pobla/files/2023-09/boib173_NNNN_saPobla.pdf).
  HTTP 200, PDF de 154264 bytes. Inspección local con `pdftotext -layout`:
  BOIB núm. 173, 07-12-2006, anuncio 21449; modificación puntual núm. 1 de las
  NNSS de Sa Pobla, aprobación definitiva con prescripciones por la Comisión
  Insular en sesión del 28-09-2006. Publica normativa y texto refundido.
  Incluye además texto ajeno al municipio en la misma página del boletín:
  no se convierte ese contenido en proyectos adicionales.

La [página municipal de trámites Urbanisme](https://sapobla.cat/ca/tramits/urbanisme)
repite el plan y otra copia del BOIB, junto con formularios de comunicación previa,
nombramiento de constructor y solicitud de licencia. Se conserva captura para
mostrar la exclusión; no constituye un registro de licencias concedidas.

## Unidad de registro y fechas

Resultado: **1 instrumento real**, `Normes subsidiàries de sa Pobla 2003`, con
**2 documentos relacionados** agrupados y con URL de procedencia municipal.
El BOIB se retiene como publicación relacionada, no como una segunda copia del
plan ni como prueba de aprobación del plan base en 2006. La modificación 1 no se
modela como expediente independiente en esta cobertura del conjunto NNSS.

La fecha `25/09/2023` pertenece a la tarjeta del archivo del portal y se conserva
como `documentos[].fecha_archivo_portal`. No es fecha de acuerdo ni publicación
del BOIB. La otra copia en Tràmits muestra `15/05/2023`, corroborando la necesidad
de separar las fechas del portal de las del instrumento. El año 2003 forma parte
del título, no proporciona un día exacto. `fecha`, `fecha_publicacion`,
`fecha_acuerdo` y `fecha_aprob` quedan nulas en el registro del plan base.
No se asigna una fase a partir de un tipo de documento o del título del fichero.

## Cobertura y limitaciones

Instantánea parcial del inventario documental NNSS publicado actualmente por el
Ayuntamiento. No garantiza vigencia jurídica completa del plan base, ni recoge
exhaustivamente modificaciones posteriores, proyectos de obras, anuncios,
contratación o archivo de expedientes. El plan territorial insular se excluye
como instrumento supramunicipal; los formularios no generan entidades.
Actualización y backfill hacen la misma instantánea completa de este alcance.

El visor oficial enlazado es https://ideib.caib.es/visor/ . No se ha verificado una
capa o geometría vinculada a este instrumento por identificador. `geometry_status:
unavailable`, geometría y coordenadas nulas, `publication_ready: false`.
No se usa centroide municipal ni jitter. El anotador compartido clasifica el
registro como `pendiente/insufficient_identity_evidence`; su existencia documental
no implica elegibilidad para publicación o concesión de licencia.

`schedule.enabled: false`, `geocode.jitter_missing: false`,
`licencias.enabled: false`. Métodos de licencias escriben vacío sin acceso a red.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```
python -m unittest municipio.test_pobla_sa -v
```

Cinco pruebas: agrupación y exclusiones, identidad municipal y separación de fechas,
deduplicación estable, rechazo de paginación/cambio de fuente, configuración,
licencias deshabilitadas y conservación de la instantánea ante documento inválido.

Extracción real mediante `load_manifest('pobla-sa')`, `load_portal_adapter(manifest)`
y `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, configurando
`manifest.portal.config['evidence_dir']` para capturas. Resultado: 1 registro,
2 documentos, HTTP 200 para las tres URLs. `evidence/validation.json` contiene
conteo `live_records`, URLs, resultado del anotador y limitaciones. HTML municipal,
HTML de Drive, PDF y texto de inspección están en `evidence/`, solo como evidencia
local, sin incorporarlos a los cuatro archivos fuente.
