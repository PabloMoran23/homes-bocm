# Mos — INE 36033, Pontevedra

Verified live on 2026-11-07 using the preinstalled runtime
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
One municipal adapter, limited to the official planning inventory linked by the
council. Scheduling, missing-coordinate jitter and licences are disabled.

## Discovery and scope

- https://www.mos.es/ — official council homepage. Its SIOTUGA image link under
  “PLANEAMENTO DO CONCELLO DE MOS” points to the exact municipality inventory:
  https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36033 .
  The homepage initially returned an HTTP 200 loading page; accepting the
  site's anonymous `dhd2` cookie exposed the actual page for discovery. The
  adapter does not depend on this council-page cookie or access any login.
- https://www.mos.es/download/ — municipal download category index. The category
  https://www.mos.es/wpdm-category/plan-xeral-de-ordenacion-municipal-de-mos-pxom/
  contains only “Modelo Alegacións PXOM”, a form. It is **not** a planning record.
- https://www.mos.es/category/obras/ — paginated news category, containing both
  actual works and political requests/general news. Excluded from this adapter;
  no claim of complete physical-works coverage or licence grants.
- The council also links the approved PXOM through a public SharePoint folder.
  This is not crawled; no credentials or personal document stores were accessed.
- The SIOTUGA public page and its
  https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js?2.5.0
  expose the inventory and document requests used by the UI. This is the actual
  current source inventory, not inferred news or search snippets.

The adapter reads **all** returned rows in class 14 (general planning: 10) and
class 13 (development planning: 9). These include the 2017 PXOM, the 2025
modification related to Galicia Sports 360, the 2024 Tameiga equipment change
of use, special/partial plans, detailed studies and older NSP modifications.
Old entries remain source-listed instruments; definitive approval does not
prove present legal validity. `vigencia_actual` is explicitly unverified.

Coverage excludes the separate historical class 16, rural delimitations class
18 and territorial-instrument inventory, as well as works, procurement and
licences. This is a partial planning inventory, not a complete municipal history.

## Extraction, grouping and semantics

The anonymous SIOTUGA form provides the `#token` nonce used in its public
requests. A fresh session obtains it on every extraction; it is not a credential.
The municipality option `36033` must identify Mos. Requests use timeouts and
reject oversized responses, HTTP errors, malformed/non-array inventories,
duplicate identities, mismatched municipal detail records and inconsistent dates.

Inventory request: POST
`https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php`
with `id=36033`, `idclase=14` or `13`, and the anonymous form nonce. The response
is a complete array; the JavaScript passes that full array to client-side
DataTables pagination. There is no server-side page limit/offset in this request.
The parser processes every element and rejects pagination envelopes rather than
silently accepting a first page. An empty combined inventory fails extraction.

For every source ID, POST
`https://siotuga.xunta.gal/siotuga/assets/inventario/getIOTPU.php`
with `iddoc=<source ID>`, `idp=0`, `lang=gl_ES` and the anonymous nonce.
`url_fuente_detalle` records the endpoint and non-session parameters for provenance;
replay uses POST and a fresh nonce, as the UI does. `url` opens the public Mos
inventory. Each instrument is one record keyed by its SIOTUGA ID, with all
`elementos.componentes` document URLs reconstructed exactly as the public UI does
from `filesroot + folder + '/documents/' + pathesperado`. Component IDs, labels
and group labels are retained. Duplicate URLs within an instrument are grouped.
No maps, chapters or appendices become separate projects. Legal-incidence data
is retained without interpreting it as current legal status.

`fechaaddef` maps only to `fecha_aprob`; BOP, DOG and BOP normative-publication
dates have separate fields. Generic `fecha`, `fecha_acuerdo` and generic
`fecha_publicacion` remain null. Missing dates are not inferred from publication
or crawl time. For example the PXOM approval is 2017-01-18, DOG publication
2017-02-08 and BOP publication 2017-06-02. The 2025 modification has approval
2025-04-14, DOG publication 2025-05-14 and BOP publication 2025-09-19.

Five genuine inventory entries explicitly return `elementos: null`: 24763,
25866, 25666, 25314 and 26186. They remain records with an empty document array
and `documentos_estado: sin documentos en SIOTUGA`. A missing `elementos` key
instead raises an error. No source document contents or coordinates are invented.
Raster/PDF plan links are not treated as verified geometry. All geometry and
coordinates remain null and `publication_ready` is false.

Update refreshes the same full snapshot; no incremental cursor can lose older
entries. Output replacement happens only after the entire extraction succeeds.

## Validation and local evidence

- `python -m unittest municipio.test_mos -v`: 7 tests passed. They cover separate
  date semantics, missing dates, complete-array processing beyond one UI page,
  rejection of forms/pagination envelopes/duplicate IDs/invalid dates, grouping,
  explicitly absent documents and wrong-municipality/detail-date failures.
- Real `MosAyuntamientoAdapter.backfill_proyectos` run through the manifest's
  class and configuration: 19 records, 703 grouped document links. No coordinates.
- Local `evidence/proyectos.jsonl` contains actual output;
  `evidence/validation.json` records count, source URLs, limitations and validation.
  `evidence/live-class-*.json`, `evidence/live-plan-*.json` and the public inventory
  HTML preserve live responses. Discovery HTML and source JavaScript are also
  captured locally. Evidence is not a source-code addition and is not committed.
- PDF sample checks are recorded in `evidence/document-checks.json`. Links beyond
  that sample are retained from SIOTUGA, not claimed individually downloaded or
  independently verified. No PDF text or geometry extraction was performed.
