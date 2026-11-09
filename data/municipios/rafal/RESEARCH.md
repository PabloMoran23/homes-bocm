# Rafal — INE 03109, Alicante

Verified live on 2026-11-09 using the preinstalled batch virtualenv. This adapter
extracts actual planning instruments from the municipal PGOU document inventory.
It is a partial planning snapshot, not a register of granted licences, a complete
works inventory, or a statement that every instrument is in force. Scheduling,
licences and coordinate jitter are disabled. All records have
`publication_ready: false` and null coordinates/geometry.

## Official source discovery

- Municipal home: https://rafal.es/ — HTTP 200, links to both the municipal PGOU
  page and the electronic-office urbanism inventory. Captured as
  `evidence/home.html`.
- Selected extraction source: https://rafal.es/?page_id=451 — HTTP 200. A PGOU
  heading and one Elementor document widget expose all base-plan documents and
  numbered modification sections 1–7 in the same response, without pagination.
  The currently working page-id URL matters: `https://www.rafal.es/pgou/` returned
  403 and `https://rafal.es/pgou/` returned 404 during discovery. The scraper uses
  the working official inventory directly, not search-engine cached content.
- Separate official inventory, linked by the municipal home:
  https://rafal.sedelectronica.es/transparency/09fbff1c-b085-40fb-a82f-b60c1cf8332f/
  — HTTP 200, urbanism folders and a “Mostrar más” control. Captured as
  `evidence/source-0.capture`. This source is discovery evidence only: its initial
  folder listing is not treated as a complete inventory or merged into results.
  In particular it displays different folder counts for modifications 3 and 6;
  the selected municipal page therefore does not claim exhaustive municipal
  document coverage.
- Representative linked PDF checks, using the non-www HTTPS host:
  https://rafal.es/wp-content/uploads/2018/04/DOGV-APROBACION-P.G.O.U.-RAFAL.pdf
  and
  https://rafal.es/wp-content/uploads/2026/05/Publicacion-DOGV-Anuncio-Modificacion-Puntual-no-7-PGOU-de-Rafal.pdf
  both returned HTTP 403. Responses and metadata are captured under `evidence/`.
  These are not successful document-content captures. Original inventory hrefs
  (including HTTP/www variants) are retained verbatim; the adapter does not
  claim to have downloaded or parsed those documents.

## Record and provenance rules

One record represents the PGOU, with its 39 plan, norms and correction links.
Each numbered modification is another record, grouping all its component
documents. The live extraction produces eight records and 60 document links:
39, 1, 1, 3, 3, 4, 5 and 4 links respectively. No map sheet, environmental report,
participation document, approval notice or multipart PDF becomes an independent
project. Stable IDs use the municipality and instrument number; order and URL
changes do not create another instrument. Every document preserves its source
label, original resolved URL and inventory URL.

Modification 6 includes a linked certificate whose label reports annulment of
the agreement. Its label and provincial Moderniza Alicante dossier URL remain
with modification 6, and the label is also emitted in
`advertencias_documentales`. Modification 7 includes an initial-approval decree
and DOGV notice alongside its two main document parts. These document labels do
not establish a definitive or current legal status. The adapter emits no inferred
`fase`. It does not inspect the annulment certificate's contents or claim that
the whole planning instrument was annulled.

The inventory provides no unambiguous publication/agreement/approval date fields.
`fecha_publicacion`, `fecha_acuerdo` and `fecha_aprob` are separately null.
Upload directory dates, page timestamps and extraction time are not event dates.
No municipal centroid, random point or inferred parcel geometry is supplied.
Forms, procurement announcements, navigation and unrelated news are outside the
selected document widget and never become records.

## Extraction and validation

The adapter requests the complete selected page with a 40-second timeout and
checks HTTP status and final municipal host. It requires the PGOU heading, a
unique document widget and nonempty instrument groups. Unexpected document
hosts, malformed modification headings, missing content and pagination fail
explicitly. All links in the widget must be municipal upload PDFs or the known
official provincial dossier route. The single-page snapshot has no page cap;
incremental update refreshes it completely with stable IDs. Errors occur before
overwriting an existing output. No electronic-office pagination is silently
truncated because that source is explicitly outside extraction coverage.

Validation performed:

- `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_rafal -v`
  — seven offline tests passed: grouping/deduplication/provenance, null dates and
  geometry, content validation, pagination rejection, unexpected links/empty
  groups, HTTP failure and snapshot updates, and manifest/registry loading.
- A real request through `load_manifest`, `load_portal_adapter` and
  `backfill_proyectos` wrote `evidence/proyectos.jsonl`: **8 actual instruments,
  60 document links**, unique IDs and correct INE identity. Shared entity policy
  annotation ran through the registry; all eight categories remain unknown,
  with policy status `ok`. No category or housing-development meaning is invented.
- `evidence/validation.json` records `live_records`, source URLs, limitations,
  test result, source checks and live adapter result. `evidence/pgou.html` is the
  response captured by the live adapter run itself. Evidence is local and is not
  part of the four source files.

Only the Rafal manifest, research note, adapter and tests are source additions.
No shared implementation or dependency changes are required.
