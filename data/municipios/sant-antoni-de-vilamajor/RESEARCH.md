# Sant Antoni de Vilamajor — INE 08198, Barcelona

Verified live on 2026-11-09 using the preinstalled batch Python runtime. One
municipal adapter covers a complete snapshot of the three current municipal
**works-project** inventories. Seven genuine projects were extracted. Coverage
of the municipality as a whole remains partial. No granted licences are claimed.
Scheduled ingestion and missing-coordinate jitter are disabled.

## Official source discovery

- [Municipal projects index](https://www.santantonidevilamajor.cat/ajuntament/projectes-municipals)
  links to all three inventories below. The live index includes the unapproved
  inventory, which was absent from the search-engine excerpt. The adapter reads
  the live index and requires its category links to match the reviewed set.
- [Public-information projects](https://www.santantonidevilamajor.cat/ajuntament/projectes-municipals/projectes-en-tramit-dinformacio-publica):
  one asphalt/sidewalk repair project, initial approval by decree on 2026-10-22.
- [Approved projects](https://www.santantonidevilamajor.cat/ajuntament/projectes-municipals/projectes-municipals-aprovats):
  five separate works projects, each described in a content block and linked to
  its project PDF in the Documents section.
- [Unapproved projects](https://www.santantonidevilamajor.cat/ajuntament/projectes-municipals/projectes-municipals-no-aprovats):
  one physical traffic-calming project for camí d'Alfou. Its document and title
  establish a real project, but the category explicitly says it is not approved.
  No agreement/publication dates are supplied or inferred from its filename.
- [Municipal planning inventory](https://www.santantonidevilamajor.cat/ajuntament/normativa/informacio-urbanistica-i-ambiental/planejament-urbanistic.html):
  separately discovered and captured, HTTP 200. Lists the POUM, ten amendments
  and four derived-planning entries, alongside an informative consolidated text
  and links to the Generalitat register and SITMUN. These instruments are outside
  this adapter's deliberately limited works-inventory scope; they are not counted
  as extracted projects or represented by fabricated dossier identifiers.
- [Transparency planning page](https://seu-e.cat/ca/web/santantonidevilamajor/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic):
  HTTP 200, captured as a second official discovery source. Provides planning
  access, not a verified public inventory of granted building licences.

No application forms, tenders, general news or page navigation become records.
No public granted-licence inventory has been verified; `licencias.enabled=false`.

## Live records and date semantics

| Project | Source narrative phase | Explicit agreement | Explicit publication |
| --- | --- | --- | --- |
| Asphalt and sidewalk repairs | Initial approval / public information | 2026-10-22 | Unknown |
| El Patronat scenic lighting | Automatic definitive approval | Initial: 2026-08-07 | Unknown |
| Pinatell sewer collector | Definitive approval | 2026-05-28 | Unknown |
| Town-hall OAC structural rehabilitation | Automatic definitive approval | Initial: 2025-11-27 | Unknown |
| 2.25 MW agrovoltaic plant | Initial approval | 2026-02-12 | Unknown |
| Alfou–Cardedeu–Llinars cycle path | Automatic definitive approval | Initial: 2025-10-13 | BOPB: 2025-10-20 |
| Camí d'Alfou traffic calming | Not approved | Unknown | Unknown |

The agrovoltaic plant is listed under approved projects but its narrative only
states initial approval; the emitted phase follows that narrative. `inventario`
preserves the source category independently.

`fecha_acuerdo` is the explicit decree/session date. Initial and definitive dates
are separately retained as `fecha_aprob_inicial` and `fecha_aprob_definitiva`.
`fecha_aprob` is the known date of the emitted approval phase: null for automatic
definitive approvals without an explicit definitive date. The three automatic
approvals are flagged and their public-information deadlines remain in the source
description, never promoted to approval dates. Generic `fecha` remains null.
Page-update timestamps are ignored. The BOPB date is parsed only where explicitly
labelled in the cycle-path narrative; source descriptions remain verbatim in
`descripcion`. No crawl dates or PDF filename dates become project dates.

## Provenance, grouping and coverage controls

Each row retains its inventory URL, canonical document link, and a `documentos`
list with document titles, URLs and originating inventory URL. Documents match
content blocks by a unique normalized title/prefix, never by position. Multiple
matching documents remain together under one project. Unmatched/ambiguous links,
missing documents and duplicate project identities across categories raise an
error. Stable IDs derive from normalized source section titles, not crawl time;
a source title change can create a new ID and requires reconciliation downstream.

The four extraction pages are unpaginated, explicit HTML lists in the captured
responses. There is no result count cap or page slice. Pagination/continuation
controls and changed category sets raise an error instead of silently truncating.
A 2 MB page limit also raises an error. HTTP requests use connection/read timeouts,
validate status, and finish all inventory parsing before atomically replacing the
output snapshot. Update refreshes this same complete current snapshot; it does not
claim a historical archive or delete/update history in a database.

All seven linked documents were checked live with ranged GETs: successful HTTP
responses and `%PDF-` signatures (details in `evidence/document-probes.json`).
Large PDFs remain links; their contents, signatures, cadastral references and
geometry have not been parsed or independently validated. No municipal centroid,
random offset or guessed geometry is substituted: `lat`, `lon`, `geometry` are
null and `publication_ready=false`. The shared entity policy labels the seven
records `unknown`; the adapter does not manufacture entity categories to bypass it.

## Validation and local evidence

- Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
- `-m unittest municipio.test_sant_antoni_de_vilamajor -v`: **6 tests passed**.
  Covers explicit/automatic approval dates, category/narrative differences,
  publication versus agreement/deadline, unapproved projects, grouped/reordered
  documents, missing/mismatched sources, pagination and preserving existing output
  when extraction fails. Manifest and registry loading are exercised.
- Real `load_portal_adapter(load_manifest(...)).backfill_proyectos(...)` run:
  **status ok, 7 records**, with the shared entity policy applied.
- Local uncommitted `evidence/proyectos.jsonl`, `evidence/validation.json`,
  `evidence/live-result.json`, `evidence/document-probes.json` and HTML captures
  preserve the output, source URLs, limitations, document checks and capture hashes.
- No shared source/dependency changes, credentials, deployment, publishing, database
  operations or git mutations were used.
