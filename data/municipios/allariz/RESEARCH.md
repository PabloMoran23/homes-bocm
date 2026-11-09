# Allariz — INE 32001, Ourense, Galicia

Verified live 2026-11-09 using the preinstalled batch Python runtime. This adapter
covers two official municipal planning document inventories, not a complete
register of municipal works or granted licences. Scheduling and licence
extraction are disabled; missing geometry is never replaced with jitter or a
municipal centroid. `publication_ready` remains false.

## Sources and discovery

- Municipal urbanism service page:
  https://www.allariz.gal/areas-municipais/urbanismo/ — HTTP 200. Describes
  services; does not contain a granted-licence inventory. Captured for discovery,
  not emitted as a project.
- Municipal planning inventory:
  https://www.allariz.gal/admin/plan-xeral-de-organizacion-municipal/ — HTTP 200.
  Contains PERI documentation, the current PXOM document collection and the
  named Plan de Encauzamento. The adapter reads every document table under the
  three reviewed section headings; it does not turn individual maps, catalogue
  entries, areas of allocation or documents into separate projects.
- Municipal dedicated PECHA portal: https://pecha.allariz.gal/ — HTTP 200.
  Identifies itself as municipal legal/technical documentation and explicitly
  labels the phase as initial approval/public exhibition. This is a separate
  instrument/version from the older PERI, not a claim of definitive approval.
  All instrument PDF links, including closed accordion contents, are present
  in server HTML. The allegation form is excluded explicitly. Repeated links
  are deduplicated by URL; an unfamiliar PDF fails for review.
- Regional cross-check discovered through official search:
  https://siotuga.xunta.gal/siotuga/urb?lang=es_ES — identifies Allariz as INE
  32001 and lists its general plan. This regional inventory is not an adapter
  input; dates or geometry from it are not silently merged into municipal data.
- https://allariz.sedelectronica.gal/ is a procedure catalogue, including an
  allegation procedure. No verified granted-licence dataset was identified;
  forms are not treated as licences. Procurement announcements and general
  news are outside this adapter's deliberately limited scope.

## Live result and provenance

Four records, with 175 unique document URLs within their respective instruments:

| Instrument | Documents | Source status/date handling |
| --- | ---: | --- |
| PERI | 2 | Table date 09/05/1995 retained on documents as `fecha_fuente`, meaning unspecified |
| Current PXOM | 67 | `vixente` comes from the section heading; no approval date inferred |
| Plan de Encauzamento | 1 | Table date 26/06/2009 retained as unspecified source date |
| PECHA initial approval/public exhibition | 105 | Phase copied from heading; no dated agreement verified |

Each record retains the inventory URL; each document retains its URL, title and
source page. All `fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob` fields
are null. Neither upload-path months nor crawl time become event dates. The PERI
and encauzamento table dates are not explicitly labelled as approval/publication
and therefore stay outside those fields. No municipal expediente number is
invented. Stable record IDs identify the four reviewed instruments/versions,
independently of document order or counts.

The full inventories are single HTML pages with no pagination observed. The
parser rejects detected pagination, missing required sections/documents,
unrecognized document-table sections, changed PECHA phase and off-host document
links. It imposes no record or document count truncation. HTTP failures,
unexpected redirects or HTML larger than 4 MB fail before replacing the output.
Updates refresh both inventories as a complete snapshot and retain the same IDs;
there is no inferred incremental cutoff.

Documents are retained as links, without attempting to parse their legal content
or parcel/building geometry. One PDF per instrument was sampled live: all four
returned HTTP 200, application/pdf and a valid PDF header. Only the initial bytes
were captured; this is not a check of every attached PDF. PDF map links are not
vector geometries. No coordinates were extracted or fabricated. The shared
entity policy marks all four records as unknown category; this does not prevent
source extraction and does not imply publication readiness.

## Validation and local evidence

Run from repository root:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_allariz -v
```

Nine tests cover document grouping, date semantics, phase retention, form
exclusion, duplicate links, missing/login content, unexpected PDFs and external
URLs, pagination rejection, manifest loading, update stability and preserving an
existing snapshot when a source fails.

A real extraction used `load_portal_adapter(load_manifest('allariz'))` and
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, with the optional
`evidence_dir` adapter config set to the local evidence directory. It produced
four genuine instrument records through the normal registry wrapper.

Local, uncommitted evidence:

- `evidence/proyectos.jsonl`: actual extraction with grouped document links.
- `evidence/validation.json`: live count, source URLs, limitations, test result
  and four sampled PDF responses.
- `evidence/pxom.html`, `evidence/pecha.html`: full HTML used by live extraction.
- `evidence/urbanismo.html`: service-page discovery capture.
- `evidence/allariz-plan-*-sample.bin`: initial PDF bytes, not complete files.

Only the four requested source files are added. No shared code, dependencies,
credentials, databases, deployment or publishing operations are involved.
